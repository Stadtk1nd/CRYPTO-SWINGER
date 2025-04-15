import pandas as pd
from indicators import calculate_indicators, validate_data

def test_indicators():
    df = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [100, 101, 102],
        "volume": [1000, 1100, 1200]
    })
    result = calculate_indicators(df, "1D")
    assert "RSI" in result.columns
    assert "MACD" in result.columns
    assert not result["RSI"].isnull().all()
    return "Test indicateurs : OK"

def test_validate_data():
    df = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02"],
        "close": [100, 200],  # Variation > 50%
        "high": [101, 201],
        "low": [99, 199],
        "volume": [1000, 1000]
    })
    is_valid, message = validate_data(df)
    assert not is_valid
    assert "anormale" in message
    return "Test validation : OK"

if __name__ == "__main__":
    st.write(test_indicators())
    st.write(test_validate_data())