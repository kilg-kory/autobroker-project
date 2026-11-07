
'''
Use body = 0.0005 for EURUSD, USDCHF, GBPUSD, USDCAD
Use body = 50 for BTCUSD
Use body = 10 for ETHUSD
Use body = 2 for XAUUSD
Use body = 10 for SP500m, UK100

'''

body = 0.0005


from util.data_utils import add_column


def signal(data, open_column, high_column, low_column, close_column, buy_column, sell_column):

    data = add_column(data, 5)

    for i in range(len(data)):

        try:

            # Bullish pattern
            if data[i - 2, close_column] < data[i - 2, open_column] and \
               abs(data[i - 2, open_column] - data[i - 2, close_column]) > body and \
               data[i - 1, close_column] < data[i - 2, open_column] and \
               data[i - 1, open_column] > data[i - 2, close_column] and \
               data[i - 1, close_column] > data[i - 1, open_column] and \
               data[i, close_column] > data[i - 2, open_column] and \
               data[i, close_column] > data[i, open_column] and \
               abs(data[i, open_column] - data[i, close_column]) > body:

                data[i + 1, buy_column] = 1

            # Bearish pattern
            elif data[i - 2, close_column] > data[i - 2, open_column] and \
                    abs(data[i - 2, close_column] - data[i - 2, open_column]) > body and \
                    data[i - 1, close_column] > data[i - 2, open_column] and \
                    data[i - 1, open_column] < data[i - 2, close_column] and \
                    data[i - 1, close_column] < data[i - 1, open_column] and \
                    data[i, close_column] < data[i - 2, open_column] and \
                    data[i, close_column] < data[i, open_column] and \
                    abs(data[i, open_column] - data[i, close_column]) > body:

                data[i + 1, sell_column] = -1

        except IndexError:

            pass

    return data
