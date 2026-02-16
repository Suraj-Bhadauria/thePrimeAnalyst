import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
    
    # Data Configuration
    DATA_PATH = "data/transactions.csv"
    
    # Agent Configuration
    MAX_ITERATIONS = 5
    VERBOSE = True
    
    # Column Definitions
    TRANSACTION_COLUMNS = {
        'transaction_id': 'Unique identifier for each transaction',
        'timestamp': 'Date and time of transaction',
        'transaction_type': 'P2P, P2M, Bill Payment, Recharge',
        'amount_inr': 'Transaction amount in Indian Rupees',
        'transaction_status': 'SUCCESS, FAILED, PENDING',
        'merchant_category': 'Category for P2M transactions: Food, Grocery, Fuel,Entertainment, Shopping, Healthcare, Education, Transport,Utilities, Other; NULL for P2P transactions',
        'sender_age_group': 'Age group of sender: 18-25, 26-35, 36-45, 46-55, 56+',
        'receiver_age_group':'Age group of receiver; only applicable for P2P transactions, NULL otherwise',
        'sender_state': 'Indian State of the sender',
        'sender_bank': "Sender's bank: SBI, HDFC, ICICI, Axis, PNB, Kotak, IndusInd, Yes Bank",
        'receiver_bank': "Receiver's bank: SBI, HDFC, ICICI, Axis, PNB, Kotak, IndusInd, Yes Bank",
        'device_type': 'Device used: Android, iOS, Web',
        'network_type': '4G, 5G, WiFi',
        'hour_of_day': 'Hour of transaction (0-23), derived from timestamp',
        'day_of_week': 'Day of transaction (Monday-Sunday), derived from timestamp',
        'is_weekend': 'Binary inductor: 0 = weekday, 1 = weekend',
        'fraud_flag': 'Binary indicator: 0 = not flagged, 1 = flagged for review;NOTE: This represents transactions flagged for review, NOT confirmed fraud cases'
    }

config = Config()