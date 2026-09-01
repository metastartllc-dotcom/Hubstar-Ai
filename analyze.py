import pandas as pd
import glob

files = glob.glob('data/input/*.xlsx')
for f in files:
    print(f"\n--- Analyzing {f} ---")
    try:
        xl = pd.ExcelFile(f)
        for sheet in xl.sheet_names:
            print(f"  Sheet: {sheet}")
            df = xl.parse(sheet)
            print(f"    Columns: {', '.join(str(c) for c in df.columns.tolist())}")
            print(f"    Rows: {len(df)}")
    except Exception as e:
        print(f"Error reading {f}: {e}")
