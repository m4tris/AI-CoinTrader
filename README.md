# 📊 Crypto Technical Analysis & GPT Recommendation Bot

This Python project performs technical analysis on Binance USDT trading pairs and uses OpenAI GPT-3.5 to recommend whether to BUY or NOT BUY.

## 🔧 Installation

1. Clone the repository:  
```bash  
git clone https://github.com/your-username/your-repo.git  
cd your-repo  
```

2. Create and activate a virtual environment:

On Linux/macOS:
```bash
python3 -m venv venv  
source venv/bin/activate  
```

On Windows:
```bash
python -m venv venv  
venv\Scripts\activate  
```
<br>

3. Install required packages:
 ```bash
  pip install -r requirements.txt  
   ```
 Or install manually:
 ```bash
pip install pandas ta requests python-dotenv openai  
```
<br>
⚙️ Environment Variables
Create a .env file in the project root with the following content:

```bash
OPENAI_API_KEY=your_openai_api_key_here  
```
<br>
🚀 How to Run
<br>
 Run the main script:
 
  ```bash
python your_script_name.py  
  ```
<br>
Make sure your internet connection is active, as the script fetches live data from Binance and calls OpenAI API.<br><br>


📄 What it Does 
```bash
• Fetches USDT trading pairs from Binance.

• Downloads recent candlestick data.

• Calculates multiple technical indicators (RSI, MACD, EMA, ATR, Bollinger Bands, etc.).

• Scores coins based on these indicators.

• Uses GPT-3.5 to get a simple BUY or NOT BUY recommendation based on the technical data.

• Prints the best scoring coin with detailed analysis.<br><br>

```



⚠️ Notes
```bash
• Respect Binance API limits to avoid being blocked.

• Make sure your OpenAI API key has enough quota.

• This is for educational purposes and not financial advice.

```








