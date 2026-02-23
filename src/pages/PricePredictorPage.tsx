
import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  TextField,
  MenuItem,
  Button,
  CircularProgress,
  Fade,
  Chip,
} from '@mui/material';
import { TrendingUp, TrendingDown, Info, Building2, BarChart2 } from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  LineElement,
  PointElement,
  TooltipItem,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Title, Tooltip, Legend
);

interface FormOptions {
  locations: string[];
  property_types: string[];
  statuses: string[];
}

interface TopFeature {
  feature: string;
  impact: number;
}

interface PredictionResponse {
  predicted_price: number;
  shap_image_base64: string;
  top_features: TopFeature[];
  base_value: number;
}

interface MarketInsights {
  status: string;
  selected_city: string;
  locations: string[];
  median_prices: number[];
  counts: number[];
}

const PricePredictorPage: React.FC = () => {
  const [formData, setFormData] = useState({
    Sqft: '',
    Location: '',
    PropertyType: '',
    Status: '',
  });

  const [formOptions, setFormOptions] = useState<FormOptions>({ locations: [], property_types: [], statuses: [] });
  const [formOptionsLoading, setFormOptionsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sqftError, setSqftError] = useState<string | null>(null);
  const [marketData, setMarketData] = useState<MarketInsights | null>(null);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [shapImgError, setShapImgError] = useState(false);

  // Load dropdown options from the backend CSV on mount
  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const res = await fetch('http://localhost:8000/form-options');
        if (res.ok) {
          const data: FormOptions = await res.json();
          setFormOptions(data);
          // Set sensible defaults: prefer Colombo 3 for location, first item otherwise
          const defaultLocation = data.locations.find(l => /colombo\s*3$/i.test(l)) || data.locations[0] || '';
          const defaultType = data.property_types.find(t => /office/i.test(t)) || data.property_types[0] || '';
          const defaultStatus = data.statuses.find(s => /rent/i.test(s)) || data.statuses[0] || '';
          setFormData(prev => ({
            ...prev,
            Location: prev.Location || defaultLocation,
            PropertyType: prev.PropertyType || defaultType,
            Status: prev.Status || defaultStatus,
          }));
        }
      } catch {
        // Fallback to model-matched values if backend unavailable
        setFormOptions({
          locations: ['Colombo 01', 'Colombo 03', 'Colombo 07', 'Dehiwala', 'Galle', 'Kandy', 'Mount Lavinia', 'Negombo', 'Nugegoda'],
          property_types: ['Building', 'Commercial Property', 'Office Space', 'Shop', 'Warehouse'],
          statuses: ['Rent', 'Sale'],
        });
        setFormData(prev => ({
          ...prev,
          Location: prev.Location || 'Colombo 03',
          PropertyType: prev.PropertyType || 'Office Space',
          Status: prev.Status || 'Rent',
        }));
      } finally {
        setFormOptionsLoading(false);
      }
    };
    fetchOptions();
  }, []);

  // Fetch market insights whenever any input field changes
  useEffect(() => {
    const fetchMarketData = async () => {
      setMarketLoading(true);
      setMarketError(null);
      try {
        const params = new URLSearchParams({
          status: formData.Status,
          location: formData.Location,
          sqft: formData.Sqft || '0',
          property_type: formData.PropertyType,
        });
        const res = await fetch(`http://localhost:8000/market-insights?${params}`);
        if (res.ok) {
          const data: MarketInsights = await res.json();
          if (data.locations && data.locations.length > 0) {
            setMarketData(data);
          } else {
            setMarketData(null);
            setMarketError('No market data found for this category.');
          }
        } else {
          setMarketError('Backend returned an error. Make sure the backend server is running.');
        }
      } catch {
        setMarketError('Could not connect to the backend. Make sure it is running on port 8000.');
      } finally {
        setMarketLoading(false);
      }
    };
    fetchMarketData();
  }, [formData.Status, formData.Location, formData.Sqft, formData.PropertyType]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    if (e.target.name === 'Sqft') setSqftError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSqftError(null);
    setError(null);
    
    if (!formData.Sqft) {
      setSqftError('Please enter the square footage.');
      return;
    }
    const sqftNum = Number(formData.Sqft);
    if (isNaN(sqftNum) || sqftNum < 50) {
      setSqftError('Square footage must be at least 50 sqft.');
      return;
    }
    if (sqftNum > 1000000) {
      setSqftError('Value is too large. Please enter a valid size.');
      return;
    }

    setLoading(true);
    setResult(null);
    setShapImgError(false);

    try {
      const response = await fetch('http://localhost:8000/predict', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          Sqft: sqftNum,
          Location: formData.Location,
          PropertyType: formData.PropertyType,
          Status: formData.Status,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get prediction from the backend.');
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-LK', {
      style: 'currency',
      currency: 'LKR',
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Strip leading zeros from district numbers for comparison:
  // "Colombo 03" and "Colombo 3" should be treated as the same city
  const normalizeCity = (s: string) =>
    s.toLowerCase().replace(/\b0+(\d+)\b/g, '$1').trim();

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f8fafc', pt: 10, pb: 8 }}>
      <Container maxWidth="lg">
        <Box sx={{ mb: 5, textAlign: 'center' }}>
          <Typography variant="h3" fontWeight="800" sx={{ color: '#0f172a', letterSpacing: '-0.02em', mb: 2 }}>
            Property Valuation <span style={{ color: '#008000' }}>Engine</span>
          </Typography>
          <Typography variant="subtitle1" sx={{ color: '#64748b', maxWidth: '600px', mx: 'auto', fontSize: '1.1rem' }}>
            Powered by XGBoost Machine Learning. Enter specifications to generate accurate market pricing and transparent XAI reasoning.
          </Typography>
        </Box>

        <Grid container spacing={4}>
          {/* Input Form Column */}
          <Grid item xs={12} md={5}>
            <Fade in timeout={600}>
              <Card elevation={0} sx={{ 
                borderRadius: 3, 
                bgcolor: 'white',
                border: '1px solid #e2e8f0',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025)',
                transition: 'transform 0.3s ease, box-shadow 0.3s ease',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                }
              }}>
                <Box sx={{ bgcolor: '#f1f5f9', py: 2.5, px: 4, borderBottom: '1px solid #e2e8f0' }}>
                <Typography variant="h6" fontWeight="700" sx={{ color: '#1e293b', display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Building2 size={20} color="#008000" />
                  Property Specifications
                </Typography>
              </Box>
              <CardContent sx={{ p: 4 }}>
                <form onSubmit={handleSubmit} noValidate>
                  <Grid container spacing={3}>
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        label="Square Footage (Sqft)"
                        name="Sqft"
                        type="number"
                        value={formData.Sqft}
                        onChange={handleChange}
                        error={!!sqftError}
                        helperText={sqftError}
                        sx={{ 
                          '& .MuiOutlinedInput-root': { 
                            borderRadius: 2,
                            '&.Mui-focused fieldset': { borderColor: '#008000' }
                          },
                          '& .MuiInputLabel-root.Mui-focused': { color: '#008000' }
                        }}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        select
                        fullWidth
                        label="Location"
                        name="Location"
                        value={formData.Location}
                        onChange={handleChange}
                        disabled={formOptionsLoading}
                        sx={{ 
                          '& .MuiOutlinedInput-root': { 
                            borderRadius: 2,
                            '&.Mui-focused fieldset': { borderColor: '#008000' }
                          },
                          '& .MuiInputLabel-root.Mui-focused': { color: '#008000' }
                        }}
                      >
                        {formOptionsLoading ? (
                          <MenuItem disabled value="">Loading locations…</MenuItem>
                        ) : formOptions.locations.map((loc) => (
                          <MenuItem key={loc} value={loc}>{loc}</MenuItem>
                        ))}
                      </TextField>
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        select
                        fullWidth
                        label="Property Type"
                        name="PropertyType"
                        value={formData.PropertyType}
                        onChange={handleChange}
                        disabled={formOptionsLoading}
                        sx={{ 
                          '& .MuiOutlinedInput-root': { 
                            borderRadius: 2,
                            '&.Mui-focused fieldset': { borderColor: '#008000' }
                          },
                          '& .MuiInputLabel-root.Mui-focused': { color: '#008000' }
                        }}
                      >
                        {formOptionsLoading ? (
                          <MenuItem disabled value="">Loading types…</MenuItem>
                        ) : formOptions.property_types.map((type) => (
                          <MenuItem key={type} value={type}>{type}</MenuItem>
                        ))}
                      </TextField>
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        select
                        fullWidth
                        label="Transaction Type"
                        name="Status"
                        value={formData.Status}
                        onChange={handleChange}
                        disabled={formOptionsLoading}
                        sx={{ 
                          '& .MuiOutlinedInput-root': { 
                            borderRadius: 2,
                            '&.Mui-focused fieldset': { borderColor: '#008000' }
                          },
                          '& .MuiInputLabel-root.Mui-focused': { color: '#008000' }
                        }}
                      >
                        {formOptionsLoading ? (
                          <MenuItem disabled value="">Loading…</MenuItem>
                        ) : formOptions.statuses.map((status) => (
                          <MenuItem key={status} value={status}>{status}</MenuItem>
                        ))}
                      </TextField>
                    </Grid>
                    <Grid item xs={12} sx={{ mt: 1 }}>
                      <Button
                        fullWidth
                        variant="contained"
                        size="large"
                        type="submit"
                        disabled={loading}
                        sx={{ 
                          py: 1.8, 
                          fontSize: '1.05rem', 
                          fontWeight: '700',
                          letterSpacing: 0.5,
                          borderRadius: 2,
                          bgcolor: '#008000',
                          textTransform: 'none',
                          boxShadow: '0 4px 14px 0 rgba(0, 128, 0, 0.25)',
                          '&:hover': {
                            bgcolor: '#006600',
                            boxShadow: '0 6px 20px rgba(0, 128, 0, 0.35)',
                          }
                        }}
                      >
                        {loading ? <CircularProgress size={28} color="inherit" /> : 'Calculate AI Valuation'}
                      </Button>
                    </Grid>
                    {error && (
                      <Grid item xs={12}>
                        <Typography color="error" variant="body2" sx={{ textAlign: 'center', mt: 1, fontWeight: 500 }}>{error}</Typography>
                      </Grid>
                    )}
                  </Grid>
                </form>
              </CardContent>
            </Card>
            </Fade>
          </Grid>

          {/* Results & XAI Column */}
          <Grid item xs={12} md={7}>
            {result ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {/* Minimalist Prediction Result Card */}
                <Fade in timeout={800}>
                  <Card elevation={0} sx={{ 
                    borderRadius: 3, 
                    bgcolor: 'white',
                    border: '1px solid #e2e8f0',
                    borderLeft: '6px solid #008000',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.05)',
                    position: 'relative',
                    transition: 'transform 0.3s ease, box-shadow 0.3s ease',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                    }
                  }}>
                    <CardContent sx={{ p: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ width: '100%', overflow: 'hidden' }}>
                      <Typography variant="overline" sx={{ color: '#64748b', letterSpacing: 1.5, fontWeight: 700, fontSize: '0.85rem' }}>
                        AI Predicted {formData.Status === 'Rent' ? 'Monthly Rent' : 'Sale Value'}
                      </Typography>
                      <Typography fontWeight="800" sx={{ 
                        color: '#0f172a', 
                        mt: 1, 
                        display: 'flex', 
                        alignItems: 'baseline', 
                        gap: { xs: 0.5, sm: 1 },
                        fontSize: { xs: '2.25rem', sm: '3rem', md: '3.75rem' },
                        flexWrap: 'wrap',
                        lineHeight: 1.2
                      }}>
                        <span style={{ fontSize: '1.25rem', color: '#008000', fontWeight: 600 }}>LKR</span>
                        <span style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
                          {formatCurrency(result.predicted_price).replace('LKR\xa0', '')}
                        </span>
                      </Typography>
                    </Box>
                    <Box sx={{ 
                      p: 2, 
                      borderRadius: '50%', 
                      bgcolor: 'rgba(0,128,0,0.06)',
                      display: { xs: 'none', sm: 'flex' } 
                    }}>
                      <TrendingUp size={40} color="#008000" />
                    </Box>
                  </CardContent>
                </Card>
                </Fade>

                {/* SHAP Explanation Card */}
                <Fade in timeout={1000}>
                  <Card elevation={0} sx={{ 
                    borderRadius: 3, 
                    bgcolor: 'white',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.05)',
                    transition: 'transform 0.3s ease, box-shadow 0.3s ease',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                    }
                  }}>
                    <Box sx={{ bgcolor: '#f1f5f9', py: 2.5, px: 4, borderBottom: '1px solid #e2e8f0' }}>
                    <Typography variant="h6" fontWeight="700" sx={{ color: '#1e293b', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Info size={20} color="#0f172a" />
                      Model Explainability (XAI)
                    </Typography>
                  </Box>
                  <CardContent sx={{ p: 4 }}>
                    <Typography variant="body1" sx={{ color: '#475569', mb: 4, lineHeight: 1.6 }}>
                      The <strong>SHAP Waterfall Plot</strong> below visualizes the exact decision path of the algorithm. It establishes the <strong>median market baseline</strong> (E[f(x)]) for this property type and applies positive/negative adjustments based on your specific inputs to arrive at the final valuation (f(x)).
                    </Typography>
                    
                    <Box sx={{ 
                        p: 2, 
                        border: '1px solid #e2e8f0', 
                        borderRadius: 2, 
                        bgcolor: 'white',
                        mb: 4
                      }}>
                      {shapImgError ? (
                        <Box sx={{ textAlign: 'center', py: 4, color: '#94a3b8' }}>
                          <Typography variant="body2" sx={{ color: '#dc2626', fontWeight: 600 }}>
                            ⚠️ SHAP plot could not be rendered. The feature impact cards below still show the top drivers.
                          </Typography>
                        </Box>
                      ) : result.shap_image_base64 ? (
                        <Box
                          component="img"
                          src={`data:image/png;base64,${result.shap_image_base64}`}
                          alt="SHAP Waterfall Explanation"
                          onError={() => setShapImgError(true)}
                          sx={{ 
                            width: '100%', 
                            height: 'auto', 
                            display: 'block'
                          }}
                        />
                      ) : (
                        <Box sx={{ textAlign: 'center', py: 4, color: '#94a3b8' }}>
                          <Typography variant="body2">SHAP plot not available from backend.</Typography>
                        </Box>
                      )}
                    </Box>

                    <Typography variant="h5" fontWeight="800" sx={{ color: '#1e293b', mb: 1, mt: 1 }}>
                      Primary Value Drivers
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#94a3b8', mb: 3, fontSize: '0.8rem' }}>
                      Each card shows the SHAP adjustment (+ or −) that feature applies to the median market baseline. Positive = above-market premium; negative = discount.
                    </Typography>
                    <Grid container spacing={3}>
                      {result.top_features.map((feature, index) => {
                        const isPositive = feature.impact > 0;
                        const featureName = feature.feature.replace('Location_', '').replace('Property Type_', '').replace('Status_', '');
                        const bgColor = isPositive ? '#f0fdf4' : '#fef2f2';
                        const borderColor = isPositive ? '#bbf7d0' : '#fecaca';
                        const textColor = isPositive ? '#166534' : '#991b1b';
                        const iconBg = isPositive ? '#dcfce7' : '#fee2e2';
                        const iconColor = isPositive ? '#16a34a' : '#dc2626';
                        const valueColor = isPositive ? '#15803d' : '#b91c1c';
                        
                        return (
                          <Grid item xs={12} sm={6} key={index}>
                            <Card elevation={0} sx={{ 
                              p: { xs: 2.5, md: 3 }, 
                              border: '1px solid',
                              borderColor: borderColor,
                              bgcolor: bgColor,
                              borderRadius: 4,
                              height: '100%',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'center',
                              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                              '&:hover': {
                                transform: 'translateY(-3px)',
                                boxShadow: isPositive ? '0 10px 15px -3px rgba(22, 163, 74, 0.1)' : '0 10px 15px -3px rgba(220, 38, 38, 0.1)'
                              }
                            }}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                <Typography variant="overline" fontWeight="800" sx={{ color: textColor, letterSpacing: 1.2, lineHeight: 1.2, mt: 0.5, pr: 2 }}>
                                  {featureName}
                                </Typography>
                                <Box sx={{ 
                                  p: 1, 
                                  borderRadius: '50%', 
                                  bgcolor: iconBg, 
                                  display: 'flex',
                                  color: iconColor
                                }}>
                                  {isPositive ? <TrendingUp size={20} strokeWidth={2.5} /> : <TrendingDown size={20} strokeWidth={2.5} />}
                                </Box>
                              </Box>
                              <Typography variant="h4" fontWeight="900" sx={{ 
                                color: valueColor, 
                                fontSize: { xs: '1.5rem', sm: '1.75rem', md: '2rem' },
                                wordBreak: 'break-word',
                                display: 'flex',
                                alignItems: 'baseline',
                                gap: 0.5
                              }}>
                                <span style={{ fontSize: '1rem', fontWeight: 700, opacity: 0.8 }}>LKR</span>
                                {isPositive ? '+' : ''}{formatCurrency(feature.impact).replace('LKR\xa0', '')}
                              </Typography>
                            </Card>
                          </Grid>
                        );
                      })}
                    </Grid>
                  </CardContent>
                </Card>
                </Fade>
              </Box>
            ) : (
              <Fade in timeout={800}>
                <Card elevation={0} sx={{ 
                  height: '100%', 
                  minHeight: '600px',
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  bgcolor: 'white', 
                  border: '1px dashed #cbd5e1', 
                  borderRadius: 3,
                  transition: 'background-color 0.3s ease, border-color 0.3s ease',
                  '&:hover': {
                    bgcolor: '#f8fafc',
                    borderColor: '#94a3b8'
                  }
                }}>
                  <CardContent sx={{ textAlign: 'center', maxWidth: '350px' }}>
                    <Box sx={{ 
                      width: '72px', 
                      height: '72px', 
                      borderRadius: '50%', 
                      bgcolor: '#f1f5f9', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      margin: '0 auto 24px auto',
                      color: '#64748b'
                    }}>
                      <Building2 size={32} />
                    </Box>
                    <Typography variant="h6" fontWeight="700" sx={{ color: '#0f172a', mb: 1.5 }}>
                      Awaiting Input
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#64748b', lineHeight: 1.6 }}>
                      Fill out the property specifications form to receive an AI-driven valuation and a full transparency breakdown of the model's logic.
                    </Typography>
                  </CardContent>
                </Card>
              </Fade>
            )}
          </Grid>
        </Grid>

        {/* Market Insights Chart Section */}
        <Box sx={{ mt: 6 }}>
          <Fade in timeout={900}>
            <Card elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 4, bgcolor: 'white', overflow: 'hidden' }}>
              <CardContent sx={{ p: { xs: 3, md: 4 } }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{ p: 1.2, borderRadius: 2, bgcolor: '#f0fdf4', color: '#008000', display: 'flex' }}>
                      <BarChart2 size={22} strokeWidth={2} />
                    </Box>
                    <Box>
                      <Typography variant="h6" fontWeight="800" sx={{ color: '#0f172a', lineHeight: 1.2 }}>
                        Market Price Comparison
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Median {formData.Status} prices by location
                        {formData.PropertyType ? ` · ${formData.PropertyType}` : ''}
                        {formData.Sqft ? ` · ~${Number(formData.Sqft).toLocaleString()} sqft` : ''}
                      </Typography>
                    </Box>
                  </Box>
                  <Chip 
                    label={`${formData.Status} Market`} 
                    size="small"
                    sx={{ bgcolor: '#f0fdf4', color: '#008000', fontWeight: 700, border: '1px solid #bbf7d0' }} 
                  />
                </Box>

                {result && (
                  <Box sx={{ mb: 2, p: 2, bgcolor: '#fef9f0', borderRadius: 2, border: '1px solid #fde68a', display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{ width: 24, height: 3, bgcolor: '#dc2626', borderRadius: 1, flexShrink: 0, borderTop: '2px dashed #dc2626' }} />
                    <Typography variant="body2" sx={{ color: '#92400e', fontWeight: 600 }}>
                      Red dashed line = Your AI Predicted Price: <strong>{formatCurrency(result.predicted_price)}</strong>
                    </Typography>
                  </Box>
                )}

                {marketLoading ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                    <CircularProgress size={36} sx={{ color: '#008000' }} />
                  </Box>
                ) : marketData && marketData.locations.length > 0 ? (
                  <Box sx={{ height: { xs: 320, md: 420 }, position: 'relative' }}>
                    <Chart
                      type="bar"
                      data={{
                        labels: marketData.locations,
                        datasets: [
                          {
                            type: 'bar' as const,
                            label: `Median ${formData.Status} Price (LKR)`,
                            data: marketData.median_prices,
                            backgroundColor: marketData.locations.map((loc, i) => {
                              const isSelected = marketData.selected_city
                                ? normalizeCity(loc) === normalizeCity(marketData.selected_city)
                                : false;
                              const lowData = (marketData.counts[i] || 0) < 8;
                              if (isSelected) return 'rgba(0, 128, 0, 0.9)';
                              return lowData ? 'rgba(0, 128, 0, 0.15)' : 'rgba(0, 128, 0, 0.25)';
                            }),
                            borderColor: marketData.locations.map((loc) => {
                              const isSelected = marketData.selected_city
                                ? normalizeCity(loc) === normalizeCity(marketData.selected_city)
                                : false;
                              return isSelected ? '#004d00' : '#008000';
                            }),
                            borderWidth: marketData.locations.map((loc) => {
                              const isSelected = marketData.selected_city
                                ? normalizeCity(loc) === normalizeCity(marketData.selected_city)
                                : false;
                              return isSelected ? 2.5 : 1;
                            }),
                            borderRadius: 6,
                          },
                          ...(result ? [{
                            type: 'line' as const,
                            label: 'Your Predicted Price',
                            data: marketData.locations.map(() => result.predicted_price),
                            borderColor: '#dc2626',
                            borderWidth: 2,
                            borderDash: [8, 4],
                            pointRadius: 0,
                            fill: false,
                            tension: 0,
                          }] : []),
                        ],
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            display: !!result,
                            labels: {
                              filter: (item: any) => item.text === 'Your Predicted Price',
                              color: '#dc2626',
                              font: { size: 12, weight: 'bold' }
                            }
                          },
                          tooltip: {
                            callbacks: {
                              label: (ctx: TooltipItem<'bar' | 'line'>) => {
                                if (ctx.dataset.type === 'line') {
                                  return `AI Predicted: LKR ${Number(ctx.parsed.y).toLocaleString('en-LK')}`;
                                }
                                const count = marketData?.counts[ctx.dataIndex];
                                const reliability = count && count >= 8 ? '✓' : '⚠ low data';
                                return [
                                  `Median: LKR ${Number(ctx.parsed.y).toLocaleString('en-LK')}`,
                                  `Listings in range: ${count ?? '—'} ${reliability}`,
                                ];
                              },
                            },
                          },
                        },
                        scales: {
                          x: {
                            grid: { display: false },
                            ticks: {
                              font: { size: 11, weight: 600 },
                              color: '#475569',
                              maxRotation: 45,
                            },
                          },
                          y: {
                            grid: { color: '#f1f5f9' },
                            ticks: {
                              callback: (value: number | string) => `${(Number(value) / 1000000).toFixed(1)}M`,
                              font: { size: 11 },
                              color: '#64748b',
                            },
                          },
                        },
                      }}
                    />
                  </Box>
                ) : (
                  <Box sx={{ textAlign: 'center', py: 6, color: '#94a3b8' }}>
                    <BarChart2 size={40} strokeWidth={1.5} />
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {marketError || 'No market data available'}
                    </Typography>
                    {marketError && (
                      <Typography variant="caption" sx={{ color: '#dc2626', mt: 1, display: 'block' }}>
                        Tip: Make sure the backend is running: <code>uvicorn app:app --reload --port 8000</code>
                      </Typography>
                    )}
                  </Box>
                )}
              </CardContent>
            </Card>
          </Fade>
        </Box>
      </Container>
    </Box>
  );
};

export default PricePredictorPage;
