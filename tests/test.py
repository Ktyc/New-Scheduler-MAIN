import pandas as pd

# Create sample data
data = {
    "Name": ["Alice Chen", "Bob Smith", "Charlie Day", "Diana Prince"],
    "Role": ["Standard", "No-PM", "Weekend-Only", "Standard"],
    "YTD": [10, 5, 0, 15],
    "Blackouts": [
        "2026-01-01, 2026-01-02", 
        "", 
        "2026-01-10", 
        "2026-01-05"
    ]
}

df = pd.DataFrame(data)

# Save to the data folder we created in Phase 1
file_path = "data/employees_template.xlsx"
df.to_excel(file_path, index=False)

print(f"Success! Template saved to {file_path}")