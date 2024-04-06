live_trade = True

# Initialize Trade Size
coin     = ["BTC", "ETH", "BNB", "BCH", "LTC"]
quantity = [0.002, 0.03, 0.15, 0.1, 0.5]

# coin     = ["BTC", "ETH", "BNB", "BCH", "LTC", "SOL"]
# quantity = [0.005, 0.05, 0.3, 0.3, 2, 1]
leverage, pair = [], []

for i in range(len(coin)):
    pair.append(coin[i] + "USDT")
    if   coin[i] == "BTC": leverage.append(75)
    elif coin[i] == "ETH": leverage.append(60)
    else: leverage.append(45)

    print("Pair Name        :   " + pair[i])
    print("Trade Quantity   :   " + str(quantity[i]) + " " + coin[i])
    print("Leverage         :   " + str(leverage[i]))
    print()

import os, time, pandas, ccxt
import requests, socket, urllib3
from termcolor import colored
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

if live_trade:
    print(colored("------ LIVE TRADE IS ENABLED ------\n", "green"))

# Get environment variables
api_key    = os.environ.get('BINANCE_KEY')
api_secret = os.environ.get('BINANCE_SECRET')
client     = Client(api_key, api_secret)

def get_timestamp():
    return int(time.time() * 1000)

def position_information(pair):
    return client.futures_position_information(symbol=pair, timestamp=get_timestamp())

def account_trades(pair, timestamp) :
    return client.futures_account_trades(symbol=pair, timestamp=get_timestamp(), startTime=timestamp)

def LONG_SIDE(response):
    if float(response[0].get('positionAmt')) > 0: return "LONGING"
    elif float(response[0].get('positionAmt')) == 0: return "NO_POSITION"
    else: return "YOU'RE FUCKED"

def SHORT_SIDE(response):
    if float(response[1].get('positionAmt')) < 0 : return "SHORTING"
    elif float(response[1].get('positionAmt')) == 0: return "NO_POSITION"
    else: return "YOU'RE FUCKED"

def change_leverage(pair, leverage):
    return client.futures_change_leverage(symbol=pair, leverage=leverage, timestamp=get_timestamp())

def change_margin_to_ISOLATED(pair):
    return client.futures_change_margin_type(symbol=pair, marginType="ISOLATED", timestamp=get_timestamp())

def set_hedge_mode(): 
    if not client.futures_get_position_mode(timestamp=get_timestamp()).get('dualSidePosition'):
        return client.futures_change_position_mode(dualSidePosition="true", timestamp=get_timestamp())

set_hedge_mode()

def market_open_long(pair, quantity):
    if live_trade:
        client.futures_create_order(symbol=pair, quantity=quantity, positionSide="LONG", type="MARKET", side="BUY", timestamp=get_timestamp())
    print(colored("🚀 GO_LONG 🚀", "green"))

def market_open_short(pair, quantity):
    if live_trade:
        client.futures_create_order(symbol=pair, quantity=quantity, positionSide="SHORT", type="MARKET", side="SELL", timestamp=get_timestamp())
    print(colored("💥 GO_SHORT 💥", "red"))

def market_close_long(pair, response):
    if live_trade:
        client.futures_create_order(symbol=pair, quantity=abs(float(response[0].get('positionAmt'))), positionSide="LONG", side="SELL", type="MARKET", timestamp=get_timestamp())
    print("💰 CLOSE_LONG 💰")

def market_close_short(pair, response):
    if live_trade:
        client.futures_create_order(symbol=pair, quantity=abs(float(response[1].get('positionAmt'))), positionSide="SHORT", side="BUY", type="MARKET", timestamp=get_timestamp())
    print("💰 CLOSE_SHORT 💰")

# Define Heikin Ashi

candlequery = 300
ccxt_client = ccxt.binance()
tohlcv_colume = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

def get_klines(pair, interval):
    return pandas.DataFrame(ccxt_client.fetch_ohlcv(pair, interval , limit=candlequery), columns=tohlcv_colume)

def heikin_ashi(klines):
    heikin_ashi_df = pandas.DataFrame(index=klines.index.values, columns=['open', 'high', 'low', 'close'])
    heikin_ashi_df['close'] = (klines['open'] + klines['high'] + klines['low'] + klines['close']) / 4

    for i in range(len(klines)):
        if i == 0: heikin_ashi_df.iat[0, 0] = klines['open'].iloc[0]
        else: heikin_ashi_df.iat[i, 0] = (heikin_ashi_df.iat[i-1, 0] + heikin_ashi_df.iat[i-1, 3]) / 2

    heikin_ashi_df['high'] = heikin_ashi_df.loc[:, ['open', 'close']].join(klines['high']).max(axis=1)
    heikin_ashi_df['low']  = heikin_ashi_df.loc[:, ['open', 'close']].join(klines['low']).min(axis=1)
    heikin_ashi_df["color"] = heikin_ashi_df.apply(color, axis=1)
    heikin_ashi_df.insert(0,'timestamp', klines['timestamp'])
    heikin_ashi_df["volume"] = klines["volume"]

    # Use Temporary Column to Identify Strength
    heikin_ashi_df["upper"] = heikin_ashi_df.apply(upper_wick, axis=1)
    heikin_ashi_df["lower"] = heikin_ashi_df.apply(lower_wick, axis=1)
    heikin_ashi_df["body"]  = abs(heikin_ashi_df['open'] - heikin_ashi_df['close'])
    heikin_ashi_df["body_s1"] = heikin_ashi_df['body'].shift(1)
    heikin_ashi_df["body_s2"] = heikin_ashi_df['body'].shift(2)
    heikin_ashi_df["indecisive"] = heikin_ashi_df.apply(is_indecisive, axis=1)
    heikin_ashi_df["candle"] = heikin_ashi_df.apply(valid_candle, axis=1)

    clean = heikin_ashi_df[["timestamp", "open", "high", "low", "close", "color", "candle"]].copy()
    return clean

def color(HA):
    if   HA['open'] < HA['close']: return "GREEN"
    elif HA['open'] > HA['close']: return "RED"
    else: return "INDECISIVE"

def upper_wick(HA):
    if HA['color'] == "GREEN": return HA['high'] - HA['close']
    elif HA['color'] == "RED": return HA['high'] - HA['open']
    else: return (HA['high'] - HA['open'] + HA['high'] - HA['close']) / 2

def lower_wick(HA):
    if HA['color'] == "GREEN": return  HA['open'] - HA['low']
    elif HA['color'] == "RED": return HA['close'] - HA['low']
    else: return (HA['open'] - HA['low'] + HA['close'] - HA['low']) / 2

def is_indecisive(HA):
    if HA['upper'] > HA['body'] and HA['lower'] > HA['body']: return True # Tweak AND/OR here
    else: return False

def valid_candle(HA):
    if not HA['indecisive']:
        if HA['color'] == "GREEN": return "GREEN"
        elif HA['color'] == "RED": return "RED"
    else: return "INDECISIVE"

def GO_LONG_CONDITION(dataset):
    if  dataset['6h'] == "GREEN" and \
        dataset['1h'] == "GREEN" and \
        dataset['3m'] == "GREEN" and \
        dataset['1m'] == "GREEN": return True
    else: return False

def GO_SHORT_CONDITION(dataset):
    if  dataset['6h'] == "RED" and \
        dataset['1h'] == "RED" and \
        dataset['3m'] == "RED" and \
        dataset['1m'] == "RED": return True
    else: return False

def EXIT_LONG_CONDITION(dataset):
    # print(dataset)
    if  dataset['1m'] != "GREEN" and dataset['3m'] != "GREEN" : return True
    else : return False

def EXIT_SHORT_CONDITION(dataset):
    # print(dataset)
    if  dataset['1m'] != "RED" and dataset['3m'] != "RED" : return True
    else : return False

def futures_wolves_rise(pair):
    # Fetch the klines data
    raw_six_hr = get_klines(pair, '6h')
    raw_one_hr = get_klines(pair, '1h')
    raw_three_min = get_klines(pair, '3m')
    raw_one_min = get_klines(pair, '1m')

    # Process Heikin Ashi 
    six_hr = heikin_ashi(raw_six_hr)[["timestamp", "candle"]].copy()
    one_hr = heikin_ashi(raw_one_hr)[["timestamp", "candle"]].copy()
    three_min = heikin_ashi(raw_three_min)[["timestamp", "candle"]].copy()
    one_min = heikin_ashi(raw_one_min)[["timestamp", "candle"]].copy()

    # Rename the column to avoid conflict
    six_hr = six_hr.rename(columns={'candle': '6h'})
    one_hr = one_hr.rename(columns={'candle': '1h'})
    three_min = three_min.rename(columns={'candle': '3m'})
    one_min = one_min.rename(columns={'candle': '1m'})

    # Merge all the necessarily data into one Dataframe
    dataset = one_min
    dataset = pandas.merge_asof(dataset, three_min, on='timestamp')
    dataset = pandas.merge_asof(dataset, one_hr, on='timestamp')
    dataset = pandas.merge_asof(dataset, six_hr, on='timestamp')

    # Apply Place Order Condition
    dataset["GO_LONG"] = dataset.apply(GO_LONG_CONDITION, axis=1)
    dataset["GO_SHORT"] = dataset.apply(GO_SHORT_CONDITION, axis=1)
    dataset["EXIT_LONG"] = dataset.apply(EXIT_LONG_CONDITION, axis=1)
    dataset["EXIT_SHORT"] = dataset.apply(EXIT_SHORT_CONDITION, axis=1)

    return dataset

# The recent 3m is messed by timestamp along with 1m, so we need to x3 for everything

def recent_minute_dumping(dataset):
    last_ten_3m = dataset.tail(30).tolist() # Recent look back the previous ten 3m candles
    if last_ten_3m.count('RED') > 6: return True # 2 x 3 = 6
    else: return False

def recent_minute_pumping(dataset):
    last_ten_3m = dataset.tail(30).tolist() # Recent look back the previous ten 3m candles
    if last_ten_3m.count('GREEN') > 6: return True # 2 x 3 = 6
    else: return False

def trend_change_to_red(dataset):
    last_3_hours = dataset.tail(240).tolist() # Recent 240 minutes aka 4 hours
    if last_3_hours.count('RED') >= 180: return True # Take 3 hours
    else: return False

def trend_change_to_green(dataset):
    last_3_hours = dataset.tail(240).tolist() # Recent 240 minutes aka 4 hours
    if last_3_hours.count('GREEN') >= 180: return True # Take 3 hours
    else: return False

taker_fees = 0.15

def debug_heikin_ashi():
    klines = get_klines("BTCUSDT", "1h")
    processed_heikin_ashi = heikin_ashi(klines)
    print("\nheikin_ashi.heikin_ashi")
    print(processed_heikin_ashi)

def debug_futures_wolves_rise():
    print(futures_wolves_rise("ETHUSDT"))

def debug_recent_minute_lookback(dataset):
    recent_minute_dumping(dataset)
    recent_minute_pumping(dataset)
    
# debug_heikin_ashi()
# debug_futures_wolves_rise()
# debug_recent_minute_lookback(debug_futures_wolves_rise())

def in_Profit(response):
    markPrice     = float(response.get('markPrice'))
    positionAmt   = abs(float(response.get('positionAmt')))
    unRealizedPNL = round(float(response.get('unRealizedProfit')), 2)
    breakeven_PNL = (markPrice * positionAmt * taker_fees) / 100
    return True if unRealizedPNL > breakeven_PNL else False

def lets_make_some_money(pair, leverage, quantity): 
    print("--------------")
    print(pair)

    # Retrieve Infomation for Initial Trade Setup
    response = position_information(pair)
    # print(response)

    if response[0].get('marginType') != "isolated": change_margin_to_ISOLATED(pair)
    if int(response[0].get("leverage")) != leverage: change_leverage(pair, leverage)

    meow = futures_wolves_rise(pair)
    # print(meow)

    long_the_dump = recent_minute_dumping(meow['3m'])
    short_the_pump = recent_minute_pumping(meow['3m'])

    red_taking_over = trend_change_to_red(meow['1h'])
    green_taking_over = trend_change_to_green(meow['1h'])

    if LONG_SIDE(response) == "NO_POSITION":
        if meow["GO_LONG"].iloc[-1] and long_the_dump:
            market_open_long(pair, quantity)
        else: print("_LONG_SIDE : 🐺 WAIT 🐺")

    if LONG_SIDE(response) == "LONGING":
        if (meow["EXIT_LONG"].iloc[-1] and in_Profit(response[0])) or (meow["6h"].iloc[-1] != "GREEN" or red_taking_over):
            market_close_long(pair, response)
        else: 
            print(colored("_LONG_SIDE : HOLDING_LONG", "green"))

    if SHORT_SIDE(response) == "NO_POSITION":
        if meow["GO_SHORT"].iloc[-1] and short_the_pump:
            market_open_short(pair, quantity)
        else: print("SHORT_SIDE : 🐺 WAIT 🐺")

    if SHORT_SIDE(response) == "SHORTING":
        if (meow["EXIT_SHORT"].iloc[-1] and in_Profit(response[1])) or (meow["6h"].iloc[-1] == "RED" or green_taking_over):
            market_close_short(pair, response)
        else: 
            print(colored("SHORT_SIDE : HOLDING_SHORT", "red"))
    print("Last action executed @ " + datetime.now().strftime("%H:%M:%S") + "\n")

    time.sleep(1)

try:
    while True:
        try:
            for i in range(len(pair)):
                init_pair     = pair[i]
                init_leverage = leverage[i]
                init_quantity = quantity[i]
                lets_make_some_money(init_pair, init_leverage, init_quantity)

        except (socket.timeout, BinanceAPIException, urllib3.exceptions.ProtocolError, urllib3.exceptions.ReadTimeoutError,
                requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout,
                ConnectionResetError, KeyError, OSError) as e:

            if not os.path.exists("ERROR"): os.makedirs("ERROR")
            with open((os.path.join("ERROR", pair[i] + ".txt")), "a", encoding="utf-8") as error_message:
                error_message.write("[!] " + pair[i] + " - " + "Created at : " + datetime.today().strftime("%d-%m-%Y @ %H:%M:%S") + "\n" + str(e) + "\n\n")
                print(e)

except KeyboardInterrupt: print("\n\nAborted.\n")
