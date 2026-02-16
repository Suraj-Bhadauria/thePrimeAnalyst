# ROUGH COMPONENT AND SNIPPET TESTING
# YOU CAN IGNORE IT




from src.utils.data_loader import data_loader


data_loader.load_data()
sample_data = data_loader.get_sample_data(5)
print(sample_data)

print('='*100)
print("==========================================")

print("COLUMN INFO")
# print("\n")
column_info = data_loader.get_column_info()
print(column_info)