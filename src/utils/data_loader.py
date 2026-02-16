# This file defines a Singleton DataLoader class that:
# Loads transaction data from a CSV
# Caches it in memory
# Preprocesses it
# Provides helper methods to access data safely
# Ensures only one instance exists

import pandas as pd
import numpy as np
from typing import Optional
from src.config import config

class DataLoader:
    _instance = None
    _df = None
    

    # this function checks if any instance is created 
    # if yes, then it loads that, otherwise it creates a new instance 
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataLoader, cls).__new__(cls)
        return cls._instance
    
    def load_data(self, force_reload: bool = False) -> pd.DataFrame:
        """Load data with caching"""
        if self._df is None or force_reload:
            print("Loading transaction data...")
            self._df = pd.read_csv(config.DATA_PATH)
            self._preprocess()
            print(f"Loaded {len(self._df):,} transactions")
        return self._df
    
    def _preprocess(self):
        """Preprocess data"""

        # 1️. Standardize column names
        self._df.columns = (
            self._df.columns
                .str.strip()
                .str.lower()
                .str.replace(" ", "_")
                .str.replace("(", "")
                .str.replace(")", "")
        )

        # 2.  Convert timestamp FIRST
        if 'timestamp' in self._df.columns:
            self._df['timestamp'] = pd.to_datetime(
                self._df['timestamp'],
                errors='coerce'
            )

            # Extract time features
            self._df['hour_of_day'] = self._df['timestamp'].dt.hour
            self._df['day_of_week'] = self._df['timestamp'].dt.dayofweek
            self._df['is_weekend'] = self._df['day_of_week'].isin([5, 6])

        # 3️.  Fix numeric & boolean types
        if 'amount_inr' in self._df.columns:
            self._df['amount_inr'] = pd.to_numeric(
                self._df['amount_inr'], errors='coerce'
            )

        if 'fraud_flag' in self._df.columns:
            self._df['fraud_flag'] = self._df['fraud_flag'].astype(bool)

        if 'is_weekend' in self._df.columns:
            self._df['is_weekend'] = self._df['is_weekend'].astype(bool)

        # 4️.  Handle missing values
        self._df.fillna({
            'fraud_flag': False,
            'is_weekend': False
        }, inplace=True)

        
    def get_column_info(self) -> dict:
        """Get column information"""
        return config.TRANSACTION_COLUMNS
    
    def get_unique_values(self, column: str) -> list:
        """Get unique values for a column"""
        if column in self._df.columns:
            return self._df[column].unique().tolist()
        return []
    
    def get_sample_data(self, n: int = 5) -> pd.DataFrame:
        """Get sample rows"""
        return self._df.head(n)


# It creates a global shared instance that can be imported anywhere.
data_loader = DataLoader()