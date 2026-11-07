from util.data_utils import add_column, del_row

def ma(data, lookback, close, position):
    data = add_column(data, 1)
    for i in range(len(data)):
        try:
            data[i, position] = (data[i - lookback + 1: i + 1, close].mean())
        except IndexError:
            pass
    data = del_row(data, lookback)
    return data
