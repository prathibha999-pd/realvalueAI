from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import joblib
import json
import re
import pandas as pd
import numpy as np
import shap
import matplotlib
matplotlib.use('Agg') # Headless backend
import matplotlib.pyplot as plt
import io
import base64
import os

app = FastAPI(title="Property Price Predictor API")

# Setup CORS to allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

models = {}
explainers = {}
columns = {}

print("Loading models and configurations...")
try:
    for status in ['sale', 'rent']:
        model_path = f'xgboost_property_model_{status}.pkl'
        cols_path = f'expected_columns_{status}.json'
        
        if os.path.exists(model_path) and os.path.exists(cols_path):
            models[status] = joblib.load(model_path)
            with open(cols_path, 'r') as f:
                columns[status] = json.load(f)
            explainers[status] = shap.Explainer(models[status])
            print(f"Loaded model for {status.capitalize()}")
        else:
            print(f"Warning: Missing files for {status} model.")
            
except Exception as e:
    print(f"Error loading models: {e}")

class PropertyRequest(BaseModel):
    Sqft: float
    Location: str
    PropertyType: str
    Status: str

def generate_shap_plot(shap_values, feature_names):
    """Generate a SHAP waterfall plot and return as base64 string"""
    # Create the SHAP plot
    shap.plots.waterfall(shap_values, show=False)
    
    # SHAP often overrides the active figure, so we grab the current one to resize it
    fig = plt.gcf()
    
    # Increase width and height to give text labels plenty of room
    fig.set_size_inches(12, 8)
    
    buf = io.BytesIO()
    
    # bbox_inches='tight' combined with pad_inches ensures no text is clipped out of bounds
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.5, dpi=120)
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

@app.post("/predict")
async def predict_price(request: PropertyRequest):
    try:
        status_key = request.Status.strip().lower()
        if status_key not in models:
            raise HTTPException(status_code=400, detail=f"No trained model available for {request.Status}")
            
        model = models[status_key]
        explainer = explainers[status_key]
        expected_cols = columns[status_key]

        # Create a DataFrame from the incoming request (excluding Status since it dictates the model)
        data = {
            'Sqft': [request.Sqft],
            'Location': [request.Location],
            'Property Type': [request.PropertyType]
        }
        df_input = pd.DataFrame(data)
        
        # One-hot encode the input
        X_encoded = pd.get_dummies(df_input, columns=['Location', 'Property Type'], drop_first=False)
        
        # Ensure all expected columns are present
        for col in expected_cols:
            if col not in X_encoded.columns:
                X_encoded[col] = 0
                
        # Reorder columns to exactly match what XGBoost expects
        X_encoded = X_encoded[expected_cols]
        
        # Make Prediction
        predicted_price = model.predict(X_encoded)[0]
        predicted_price = max(0, float(predicted_price))
        
        # FIX: warn + log if price was clipped (indicates model issue or extreme input)
        was_clipped = float(predicted_price) < 0
        predicted_price = max(0, float(predicted_price))
        if was_clipped:
            print(f"[WARN] Negative prediction clipped to 0 for input: {request.dict()}")

        # Generate SHAP explanation
        shap_values = explainer(X_encoded)
        sv_instance = shap_values[0]

        # Generate the waterfall plot image
        shap_image_b64 = generate_shap_plot(sv_instance, expected_cols)

        # Extract top features — only include features that are "active":
        # - Sqft always included (continuous)
        # - One-hot features included only when value == 1 (user's actual selection)
        encoded_values = X_encoded.iloc[0].to_dict()
        feature_impacts = {}
        for col, shap_val in zip(expected_cols, sv_instance.values):
            is_onehot = any(col.startswith(p) for p in ['Location_', 'Property Type_', 'Status_'])
            if is_onehot and encoded_values.get(col, 0) == 0:
                continue  # skip inactive one-hot features
            feature_impacts[col] = float(shap_val)

        sorted_impacts = sorted(feature_impacts.items(), key=lambda x: abs(x[1]), reverse=True)
        top_features = [{"feature": k, "impact": v} for k, v in sorted_impacts[:5]]

        # location_known: True if the exact location column was in expected_cols
        location_col = f"Location_{request.Location}"
        location_known = location_col in expected_cols

        return {
            "predicted_price": predicted_price,
            "shap_image_base64": shap_image_b64,
            "top_features": top_features,
            "base_value": float(sv_instance.base_values),
            "location_known": location_known,
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    try:
        metrics = {}
        for status in ['sale', 'rent']:
            path = f'eval_metrics_{status}.json'
            if os.path.exists(path):
                with open(path, 'r') as f:
                    metrics[status] = json.load(f)
        
        if not metrics:
            return {"error": "Metrics files not found. Models might not be trained."}
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/form-options")
async def get_form_options():
    """
    Derives dropdown options from the expected_columns JSON files — guaranteeing
    the values match exactly what the model was trained on.
    """
    try:
        locations_set: set = set()
        property_types_set: set = set()
        statuses = ["Rent", "Sale"]

        for status in ["rent", "sale"]:
            cols_path = f"expected_columns_{status}.json"
            if not os.path.exists(cols_path):
                continue
            with open(cols_path, "r") as f:
                cols = json.load(f)

            for col in cols:
                if col.startswith("Location_"):
                    val = col[len("Location_"):]
                    if val.lower() != "other":   # skip catch-all
                        locations_set.add(val)
                elif col.startswith("Property Type_"):
                    val = col[len("Property Type_"):]
                    if val.lower() != "other":
                        property_types_set.add(val)

        return {
            "locations":      sorted(locations_set),
            "property_types": sorted(property_types_set),
            "statuses":       statuses,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def extract_city(raw: str) -> str:
    """
    Extract a clean city token from a raw address string.
    Identical to the function in train_model.py — must stay in sync.
    e.g. 'No 5, Park Street, Colombo 00200'  -> 'Colombo 2'
         'Galle Road, Mount Lavinia'          -> 'Mount Lavinia'
         'Rajagiriya'                         -> 'Rajagiriya'
    """
    if not isinstance(raw, str):
        return 'Other'
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    for part in reversed(parts):
        if re.fullmatch(r'[\d\s]+', part):
            continue
        if part.lower().startswith('sri lanka'):
            continue
        clean = re.sub(r'\s+\d{4,}$', '', part).strip()
        if clean:
            clean = re.sub(r'\b0+(\d+)\b', r'\1', clean)
            return clean
    return parts[-1] if parts else 'Other'

# Keep alias so existing references in this file still work
normalize_location = extract_city


@app.get("/market-insights")
async def get_market_insights(
    status: str = "Rent",
    location: str = "",
    sqft: float = 0,
    property_type: str = ""
):
    """
    Returns median price per city for properties matching the user's inputs:
    - status (Rent/Sale)
    - property_type (e.g. 'Office Space') — mapped to training categories
    - sqft: filters to properties within ±30% of the entered size
    - location: always included in results; normalised name returned for highlighting
    """
    try:
        csv_files = sorted(
            [f for f in os.listdir('.') if f.endswith('.csv')],
            reverse=True
        )
        if not csv_files:
            raise HTTPException(status_code=404, detail="No dataset CSV file found.")

        csv_path = csv_files[0]
        df = pd.read_csv(csv_path, header=None)
        df.columns = ['Title', 'Sqft', 'Property Type', 'URL', 'Location',
                      'Description', 'Image', 'Price', 'Status', 'Source', 'Date']

        # Normalise location strings
        df['Location'] = df['Location'].astype(str).str.strip().str.rstrip(',').str.strip()
        df['City'] = df['Location'].apply(normalize_location)
        selected_city = normalize_location(location) if location.strip() else ""

        # Apply same property type mapping as training
        PT_MAP = {
            'office': 'Office Space', 'office space': 'Office Space',
            'co-working': 'Office Space', 'co-working space': 'Office Space',
            'shop': 'Shop', 'shop space': 'Shop', 'shopping mall': 'Shop', 'restaurant': 'Shop',
            'warehouse': 'Warehouse', 'warehouse / storage': 'Warehouse',
            'factory': 'Warehouse', 'factory / workshop': 'Warehouse',
            'building': 'Building',
            'hotel': 'Commercial Property', 'guest house': 'Commercial Property',
            'multipurpose': 'Commercial Property', 'other': 'Commercial Property',
        }
        df['Property Type'] = df['Property Type'].astype(str).str.strip().str.lower().map(PT_MAP).fillna('Commercial Property')

        # Ensure numeric columns
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        df['Sqft'] = pd.to_numeric(df['Sqft'], errors='coerce')
        df = df.dropna(subset=['Price', 'Sqft'])
        df = df[df['Sqft'] >= 50]   # remove nonsensical tiny entries

        # --- Filter by status ---
        df_filtered = df[df['Status'].str.lower() == status.lower()].copy()

        # --- Filter by property type (if provided) ---
        if property_type.strip():
            mapped_type = PT_MAP.get(property_type.strip().lower(), property_type.strip())
            pt_mask = df_filtered['Property Type'] == mapped_type
            if pt_mask.sum() >= 10:
                df_filtered = df_filtered[pt_mask]

        # --- Filter by sqft band ±30% (tighter than before) ---
        if sqft and sqft > 0:
            lo, hi = sqft * 0.70, sqft * 1.30
            sqft_mask = df_filtered['Sqft'].between(lo, hi)
            if sqft_mask.sum() >= 8:
                df_filtered = df_filtered[sqft_mask]

        # --- Remove price outliers (10th–90th percentile) ---
        q1 = df_filtered['Price'].quantile(0.10)
        q3 = df_filtered['Price'].quantile(0.90)
        df_filtered = df_filtered[(df_filtered['Price'] >= q1) & (df_filtered['Price'] <= q3)]


        # --- Group by city ---
        location_stats = (
            df_filtered.groupby('City')['Price']
            .agg(['median', 'count'])
            .reset_index()
        )
        location_stats.columns = ['location', 'median_price', 'count']
        location_stats = location_stats[location_stats['count'] >= 2]
        location_stats = location_stats.sort_values('median_price', ascending=False)

        # Stash the selected city row before slicing to top 15
        selected_row = None
        if selected_city:
            sel = location_stats[location_stats['location'].str.lower() == selected_city.lower()]
            if not sel.empty:
                selected_row = sel.iloc[[0]]

        top15 = location_stats.head(15)

        # Always include selected city even if outside top 15
        if selected_row is not None:
            already_in = top15['location'].str.lower().eq(selected_city.lower()).any()
            if not already_in:
                top15 = pd.concat([top15, selected_row], ignore_index=True)

        return {
            "status": status,
            "selected_city": selected_city,
            "locations": top15['location'].tolist(),
            "median_prices": [round(float(p), 2) for p in top15['median_price'].tolist()],
            "counts": top15['count'].tolist()
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

