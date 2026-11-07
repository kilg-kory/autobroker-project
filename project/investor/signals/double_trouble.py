# import numpy as np
# import matplotlib.pyplot as plt

# hv_noise = np.random.normal(0, 1, 250)
# lv_noise = np.random.normal(0, 0.1, 250)

# plt.plot(hv_noise, color="red", label="High Volatility")
# plt.plot(lv_noise, color="blue", label="Low Volatility")
# plt.axhline(y=0, color="green", linewidth = 1)
# plt.grid()
# plt.show()

from util.data_utils import add_column
from indicators.atr import atr

#trend following
def signal(data, open_column, high_column, low_column, close_column, atr_column, buy_column, sell_column):
    data = add_column(data, 5)

    for i in range(len(data)):
        try:
          # Bullish pattern
            if data[i, close_column] > data[i, open_column] and \
               data[i, close_column] > data[i - 1, close_column] and \
               data[i - 1, close_column] > data[i - 1, open_column] and \
               data[i, high_column] - data[i, low_column] > (2 * data[i - 1, atr_column]) and \
               data[i, close_column] - data[i, open_column] > data[i - 1, close_column] - data[i - 1, open_column] and \
               data[i, buy_column] == 0:

                data[i + 1, buy_column] = 1
            # Bearish pattern
            elif data[i, close_column] < data[i, open_column] and \
                    data[i, close_column] < data[i - 1, close_column] and \
                    data[i - 1, close_column] < data[i - 1, open_column] and \
                    data[i, high_column] - data[i, low_column] > (2 * data[i - 1, atr_column]) and \
                    data[i, open_column] - data[i, close_column] > data[i - 1, open_column] - data[i - 1, close_column] and \
                    data[i, sell_column] == 0:

                data[i + 1, sell_column] = -1

        except IndexError:
            pass
    return data
