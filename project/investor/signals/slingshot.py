from util.data_utils import add_column

#trend following
def signal(data, open_column, high_column, low_column, close_column, buy_column, sell_column):
    data = add_column(data, 5)

    for i in range(len(data)):
        try:
            # Bullish pattern
            if data[i, close_column] > data[i - 1, high_column] and \
                    data[i, close_column] > data[i - 2, high_column] and \
                    data[i, low_column] <= data[i - 3, high_column] and \
                    data[i, close_column] > data[i, open_column] and \
                    data[i - 1, close_column] >= data[i - 3, high_column] and \
                    data[i - 2, low_column] >= data[i - 3, low_column] and \
                    data[i - 2, close_column] > data[i - 2, open_column] and \
                    data[i - 2, close_column] > data[i - 3, high_column] and \
                    data[i - 1, high_column] <= data[i - 2, high_column]:

                data[i + 1, buy_column] = 1

            # Bearish pattern
            elif data[i, close_column] < data[i - 1, low_column] and \
                    data[i, close_column] < data[i - 2, low_column] and \
                    data[i, high_column] >= data[i - 3, low_column] and \
                    data[i, close_column] < data[i, open_column] and \
                    data[i - 1, high_column] <= data[i - 3, high_column] and \
                    data[i - 2, close_column] <= data[i - 3, low_column] and \
                    data[i - 2, close_column] < data[i - 2, open_column] and \
                    data[i - 2, close_column] < data[i - 3, low_column] and \
                    data[i - 1, low_column] >= data[i - 2, low_column]:

                data[i + 1, sell_column] = -1

        except IndexError:
            pass

    return data
