'''
Use body = 0.0005 for EURUSD, USDCHF, GBPUSD, USDCAD
Use body = 50 for BTCUSD
Use body = 10 for ETHUSD
Use body = 2 for XAUUSD
Use body = 5 for SP500m, UK100

Use wick = 0.0002 for EURUSD, USDCHF, GBPUSD, USDCAD
Use wick = 10 for BTCUSD
Use wick = 2 for ETHUSD
Use wick = 0.5 for XAUUSD
Use wick = 3 for SP500m, UK100

'''

body = 0.0005
wick = 0.0002

'''
Use my_data = rounding(my_data, 4) for EURUSD, USDCHF, GBPUSD, USDCAD
Use my_data = rounding(my_data, 0) for BTCUSD, ETHUSD, XAUUSD, SP500m, UK100

'''



from util.data_utils import add_column, rounding


def signal(data, open_column, high_column, low_column, close_column, buy_column, sell_column):

    data = add_column(data, 5)
    # Округление делает вызывающий код: rounding(my_data, 4) для FX, 0 для BTC/индексов

    for i in range(len(data)):  
        
       try:
           
            # Bullish pattern
            if data[i, close_column] > data[i, open_column] and \
               abs(data[i - 1, close_column] - data[i - 1, open_column]) < body and \
               min(data[i - 1, close_column], data[i - 1, open_column]) - data[i - 1, low_column] > 2 * wick and \
               data[i - 1, close_column] == data[i - 1, high_column] and \
               data[i - 2, close_column] < data[i - 2, open_column]:
                   
                     data[i + 1, buy_column] = 1 
                     
            # Bearish pattern
            elif data[i, close_column] < data[i, open_column] and \
                 abs(data[i - 1, close_column] - data[i - 1, open_column]) < body and \
                 data[i - 1, high_column] - max(data[i - 1, close_column], data[i - 1, open_column]) > 2 * wick and \
                 data[i - 1, close_column] == data[i - 1, low_column] and \
                 data[i - 2, close_column] > data[i - 2, open_column]:
                     
                     data[i + 1, sell_column] = -1                      
                    
       except IndexError:
            
            pass
        
    return data
