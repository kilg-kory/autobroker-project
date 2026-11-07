from util.data_utils import add_column, rounding


"""
 Before checking the
results, let’s recap the trading conditions mentioned previously:
• The entry is done on the next open price after the validation of the signal on the
current close price.
• The exit is done upon getting another signal in either direction (bullish or
bearish).
• The transaction costs are omitted from the performance evaluation metrics.
• There is no risk management system
"""

#  Contrarian Pattern

# интересно, что этот паттерн наёбывает меня сразу же, выдавая 100% ложный результат.
# ещё интересней, что он начинает хорошо работать, если его перевернуть.
# видимо под каждый инструмент нужно прокатывать тест на эффективность каждого паттерна.
def signal(data, open_column, close_column, buy_column, sell_column):

    data = add_column(data, 5)
    data = rounding(data, 4)    
    
    for i in range(len(data)):
        try:

           # Bullish pattern
           if data[i, close_column] > data[i, open_column] and \
              data[i, close_column] > data[i - 1, close_column] and \
              data[i - 1, close_column] == data[i - 1, open_column] and \
              data[i - 2, close_column] < data[i - 2, open_column] and \
              data[i - 2, close_column] < data[i - 2, open_column]:
                  
                    data[i + 1, buy_column] = 1 
                    
           # Bearish pattern
           elif data[i, close_column] < data[i, open_column] and \
              data[i, close_column] < data[i - 1, close_column] and \
              data[i - 1, close_column] == data[i - 1, open_column] and \
              data[i - 2, close_column] > data[i - 2, open_column] and \
              data[i - 2, close_column] > data[i - 2, open_column]:
                  
                    data[i + 1, sell_column] = -1 
        except IndexError:

            pass

    return data
