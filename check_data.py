import pandas as pd
df = pd.read_csv('data/patient_vitals.csv')

# Check which vital columns have data
vital_cols = ['heart_rate', 'systolic_bp', 'diastolic_bp', 'respiratory_rate', 
              'spo2', 'temperature_f', 'mean_arterial_pressure']

for col in vital_cols:
    if col in df.columns:
        non_null = df[col].notna().sum()
        total = len(df)
        print(f"{col}: {non_null}/{total} ({100*non_null/total:.1f}%)")
    else:
        print(f"{col}: NOT IN DATASET")