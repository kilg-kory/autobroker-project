from util.data_utils import add_column

'''
Use body = 0.0005 for EURUSD, USDCHF, GBPUSD, USDCAD
Use body = 50 for BTCUSD
Use body = 10 for ETHUSD
Use body = 2 for XAUUSD
Use body = 10 for SP500m, UK100

'''
body = 0.0005  # body i = |close price i - open price i|

def three_white_soldiers(data, i, open_column, close_column):
    return data[i, close_column] - data[i, open_column] > body and \
        data[i - 1, close_column] - data[i - 1, open_column] > body and \
        data[i - 2, close_column] - data[i - 2, open_column] > body and \
        data[i, close_column] > data[i - 1, close_column] and \
        data[i - 1, close_column] > data[i - 2, close_column] and \
        data[i - 2, close_column] > data[i - 3, close_column]


def three_black_crows(data, i, open_column, close_column):
    return data[i, close_column] - data[i, open_column] > body and \
        data[i - 1, close_column] - data[i - 1, open_column] > body and \
        data[i - 2, close_column] - data[i - 2, open_column] > body and \
        data[i, close_column] < data[i - 1, close_column] and \
        data[i - 1, close_column] < data[i - 2, close_column] and \
        data[i - 2, close_column] < data[i - 3, close_column]

#trend following
def the_three_candies_pattern(data, open_column, close_column, buy_column, sell_column):
    data = add_column(data, 5)
   

    for i in range(len(data)):
        try:
            if three_white_soldiers(data, i, open_column, close_column) and data[i, buy_column] == 0:
                data[i + 1, buy_column] = 1
            elif three_black_crows(data, i, open_column, close_column) and data[i, sell_column] == 0:
                data[i + 1, sell_column] = -1
        except IndexError:
            pass
    return data
