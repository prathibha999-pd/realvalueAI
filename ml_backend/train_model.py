import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import joblib
import json
import os
import re
import glob

# ==========================================
# 1. Load Data
# ==========================================
print("Loading dataset...")
latest_csv = max(glob.glob('property_data_*.csv'), key=os.path.getctime)
print(f"Using {latest_csv}")

column_names = ['Title', 'Sqft', 'Property Type', 'Link', 'Location',
                'Address', 'Image URL', 'Price', 'Status', 'Source', 'Scrape Date']

df = pd.read_csv(latest_csv, names=column_names, header=None,
                 engine='python', on_bad_lines='skip')

# Remove header rows mixed into data
df = df[df['Price'] != 'Price']
df.columns = df.columns.str.strip()

# Filter out missing / N/A values
df = df[df['Price'].notna() & df['Sqft'].notna()]
df = df[df['Price'] != 'N/A']
df = df[df['Sqft']  != 'N/A']

df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
df['Sqft']  = pd.to_numeric(df['Sqft'],  errors='coerce')
df = df.dropna(subset=['Price', 'Sqft'])

# Remove clearly erroneous entries (< 50 sqft or price = 0)
df = df[df['Sqft']  >= 50]
df = df[df['Price'] > 0]

# ==========================================
# 1.5  Clean Property Type
# ==========================================
property_type_map = {
    'office':              'Office Space',
    'office space':        'Office Space',
    'co-working':          'Office Space',
    'co-working space':    'Office Space',
    'shop':                'Shop',
    'shop space':          'Shop',
    'shopping mall':       'Shop',
    'restaurant':          'Shop',
    'warehouse':           'Warehouse',
    'warehouse / storage': 'Warehouse',
    'factory':             'Warehouse',
    'factory / workshop':  'Warehouse',
    'building':            'Building',
    'hotel':               'Commercial Property',
    'guest house':         'Commercial Property',
    'multipurpose':        'Commercial Property',
    'other':               'Commercial Property',
}
df['Property Type'] = (df['Property Type']
                        .str.strip()
                        .str.lower()
                        .map(property_type_map)
                        .fillna('Commercial Property'))

# ==========================================
# 1.6  Clean Location → City name
# ==========================================
def extract_city(raw: str) -> str:
    """
    Extract a clean city token from a raw address string, e.g.:
      'No 5, Park Street, Colombo 00200'  -> 'Colombo 2'
      'Rajagiriya'                         -> 'Rajagiriya'
      'Galle Road, Mount Lavinia'          -> 'Mount Lavinia'
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
            # Normalise leading zeros: "Colombo 03" → "Colombo 3"
            clean = re.sub(r'\b0+(\d+)\b', r'\1', clean)
            return clean
    return parts[-1] if parts else 'Other'

df['Location'] = df['Location'].astype(str).str.strip().str.rstrip(',').str.strip()
df['Location'] = df['Location'].apply(extract_city)

# ==========================================
# 2. Train Sale & Rent Models
# ==========================================
def train_specific_model(df_subset, status_label):
    print(f"\n{'='*50}")
    print(f"Training model for: {status_label}")
    print(f"{'='*50}")

    if len(df_subset) < 20:
        print(f"Not enough data ({len(df_subset)} rows) to train {status_label} model.")
        return

    # ---- FIX #5: Outlier removal PER property-type group ----
    # This prevents a 10,000 sqft warehouse's price from distorting the
    # outlier cutoffs that apply to 200 sqft offices.
    cleaned_groups = []
    for pt, grp in df_subset.groupby('Property Type'):
        q_lo = grp['Price'].quantile(0.05)
        q_hi = grp['Price'].quantile(0.95)
        cleaned_groups.append(grp[(grp['Price'] >= q_lo) & (grp['Price'] <= q_hi)])
    df_clean = pd.concat(cleaned_groups).copy()
    print(f"Rows after per-group outlier removal: {len(df_clean)} (was {len(df_subset)})")

    # ---- Keep only cities with enough listings; collapse the rest to 'Other' ----
    MIN_LISTINGS = 10
    city_counts = df_clean['Location'].value_counts()
    rare_cities  = city_counts[city_counts < MIN_LISTINGS].index
    df_clean['Location'] = df_clean['Location'].replace(rare_cities, 'Other')

    known_cities = sorted(df_clean['Location'].unique().tolist())
    print(f"Location categories ({len(known_cities)}): {known_cities}")
    print(f"Property Type categories: {sorted(df_clean['Property Type'].unique().tolist())}")

    features = ['Sqft', 'Location', 'Property Type']
    X = df_clean[features].copy()
    y = df_clean['Price'].copy()

    X_encoded = pd.get_dummies(X, columns=['Location', 'Property Type'], drop_first=False)
    expected_columns = list(X_encoded.columns)

    with open(f'expected_columns_{status_label.lower()}.json', 'w') as f:
        json.dump(expected_columns, f)
    print(f"Saved {len(expected_columns)} expected columns.")

    X_temp, X_test, y_temp, y_test = train_test_split(
        X_encoded, y, test_size=0.15, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.1765, random_state=42)

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # FIX #1: early_stopping_rounds moved to constructor (removes deprecation warning)
    model = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=1,
        random_state=42,
        early_stopping_rounds=30,          # <-- in constructor, not fit()
        # Quantile regression at alpha=0.5 predicts the MEDIAN price.
        # This prevents systematic overprediction on right-skewed price data
        # and aligns AI predictions with the market median chart.
        objective='reg:quantileerror',
        quantile_alpha=0.5,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=50,
    )

    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae  = mean_absolute_error(y_test, y_pred)
    r2   = r2_score(y_test, y_pred)

    # FIX #2: Pinball loss (= quantile loss at 0.5) is the true metric for this model.
    # R² is included for reference but can be misleading for quantile models.
    pinball = np.mean(np.maximum(0.5 * (y_test - y_pred), (0.5 - 1) * (y_test - y_pred)))

    print(f"\n--- {status_label} Model Evaluation ---")
    print(f"Pinball Loss (↓ better): LKR {pinball:>15,.2f}")
    print(f"MAE:                     LKR {mae:>15,.2f}")
    print(f"RMSE:                    LKR {rmse:>15,.2f}")
    print(f"R² (informational):      {r2:.4f}")

    eval_metrics = {
        'rmse': float(rmse),
        'mae': float(mae),
        'r2': float(r2),
        'pinball_loss': float(pinball),
        'objective': 'quantile_median',
    }
    with open(f'eval_metrics_{status_label.lower()}.json', 'w') as f:
        json.dump(eval_metrics, f)

    model_filename = f'xgboost_property_model_{status_label.lower()}.pkl'
    joblib.dump(model, model_filename)
    print(f"Model saved → {model_filename}")

# ---- Run training for both statuses ----
df_sale = df[df['Status'].str.lower() == 'sale'].copy()
df_rent = df[df['Status'].str.lower() == 'rent'].copy()

train_specific_model(df_sale, 'Sale')
train_specific_model(df_rent, 'Rent')

print("\nAll models trained successfully.")
