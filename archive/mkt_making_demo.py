import requests
import numpy as np
from time import sleep

s = requests.Session()
s.headers.update({'X-API-key': 'Your Key'})

MAX_LONG_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
MAX_GROSS_EXPOSURE = 25000
ORDER_LIMIT = 5000


def get_tick():
    resp = s.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status']


def get_bid_ask(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/securities/book', params=payload)
    if resp.ok:
        book = resp.json()
        bid_side_book = book['bids']
        ask_side_book = book['asks']

        bid_prices_book = [item["price"] for item in bid_side_book]
        ask_prices_book = [item['price'] for item in ask_side_book]

        best_bid_price = bid_prices_book[0]
        best_ask_price = ask_prices_book[0]
        bid_std = (bid_prices_book - np.mean(bid_prices_book)) / np.std(bid_prices_book)
        ask_std = (ask_prices_book - np.mean(ask_prices_book)) / np.std(ask_prices_book)
        return best_bid_price, best_ask_price, bid_prices_book[:5], ask_prices_book[:5]


def get_time_sales(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/securities/tas', params=payload)
    if resp.ok:
        book = resp.json()
        time_sales_book = [item["quantity"] for item in book]
        return time_sales_book


def get_position():
    resp = s.get('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        net = book[0]['position'] + book[1]['position'] + book[2]['position']
        gross = abs(book[0]['position']) + abs(book[1]['position']) + abs(book[2]['position'])
        return net, gross, [tickers["position"] for tickers in book]


def get_open_orders(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/orders', params=payload)
    if resp.ok:
        orders = resp.json()
        buy_orders = [item for item in orders if item["action"] == "BUY"]
        sell_orders = [item for item in orders if item["action"] == "SELL"]
        return buy_orders, sell_orders


def get_order_status(order_id):
    resp = s.get('http://localhost:9999/v1/orders' + '/' + str(order_id))
    if resp.ok:
        order = resp.json()
        return order['status']


def main():
    tick, status = get_tick()
    ticker_list = ['CNR', 'RY', 'AC']

    while status == 'ACTIVE':

        for i in range(3):
            ticker_symbol = ticker_list[i]
            buy_order, sell_order = get_open_orders(ticker_symbol)
            net, gross, list_net = get_position()
            best_bid_price, best_ask_price, bid_book, ask_book = get_bid_ask(ticker_symbol)
            pending_buy, pending_sell = len(buy_order) * ORDER_LIMIT, len(sell_order) * ORDER_LIMIT
            inv_quant = min(abs(list_net[i]), 5000)
            if list_net[i] < 0:
                print(f"should buy {ticker_symbol}")
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': inv_quant,
                                      'price': (bid_book[1] + bid_book[2]) / 2, 'action': 'BUY'})
                print(resp.json())
            if list_net[i] > 0:
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': inv_quant,
                                      'price': (ask_book[1] + ask_book[2]) / 2, 'action': 'SELL'})
                print(resp.json())
            if list_net[i] > 0:
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': inv_quant,
                                      'price': (best_bid_price + best_ask_price) / 2, 'action': 'SELL'})
                print(f"sub sell {ticker_symbol}, {(best_bid_price + best_ask_price) / 2}")
            elif list_net[i] < 0:
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': inv_quant,
                                      'price': (best_bid_price + best_ask_price) / 2, 'action': 'BUY'})
                print(f"sub buy {ticker_symbol}, {(best_bid_price + best_ask_price) / 2}")

            if gross <= MAX_GROSS_EXPOSURE - (pending_buy + pending_sell):
                if best_ask_price - best_bid_price >= 0.05:
                    if list_net[i] < 4 * ORDER_LIMIT:
                        resp = s.post('http://localhost:9999/v1/orders',
                                      params={'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': ORDER_LIMIT,
                                              'price': bid_book[1], 'action': 'BUY'})
                    if list_net[i] > -4 * ORDER_LIMIT:
                        resp = s.post('http://localhost:9999/v1/orders',
                                      params={'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': ORDER_LIMIT,
                                              'price': ask_book[1], 'action': 'SELL'})

            sleep(0.2)
            s.post('http://localhost:9999/v1/commands/cancel', params={'ticker': ticker_symbol})

        tick, status = get_tick()


if __name__ == '__main__':
    main()
