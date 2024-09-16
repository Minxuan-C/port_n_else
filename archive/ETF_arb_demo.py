import requests
from time import sleep
import numpy as np

s = requests.Session()
s.headers.update({'X-API-key': 'Your Key'})

# global variables
MAX_LONG_EXPOSURE_NET = 25000
MAX_SHORT_EXPOSURE_NET = -25000
MAX_EXPOSURE_GROSS = 500000
ORDER_LIMIT = 50000


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

        return best_bid_price, best_ask_price


def get_time_sales(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/securities/tas', params=payload)
    if resp.ok:
        book = resp.json()
        time_sales_book = [item["quantity"] for item in book]
        return time_sales_book


def get_position(index_only=False):
    resp = s.get('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        if index_only == True:
            index_position = book[3]['position']
            return index_position
        else:
            gross_position = abs(book[1]['position']) + abs(book[2]['position']) + 2 * abs(book[3]['position'])
            net_position = book[1]['position'] + book[2]['position'] + 2 * book[3]['position']
            return gross_position, net_position


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


def create_lease():
    resp_get_lease = s.get('http://localhost:9999/v1/leases')
    if len(resp_get_lease.json()) == 0:
        resp = s.post('http://localhost:9999/v1/leases', params={'ticker': 'ETF-Creation'})
        resp = s.post('http://localhost:9999/v1/leases', params={'ticker': 'ETF-Redemption'})
    return (resp_get_lease.json()[0]["id"], resp_get_lease.json()[1]["id"])

    ### Info about all available leases
    resp = s.get('http://localhost:9999/v1/assets')
    all_leases = resp.json()

    ### Info about the available ETF-Creation lease
    resp = s.get('http://localhost:9999/v1/assets', params={'ticker': 'ETF-Creation'})
    creation_lease = resp.json()

    ### Info about open leases
    resp = s.get('http://localhost:9999/v1/leases')
    leases = resp.json()

    ### open the ETF-Creation lease
    resp = s.post('http://localhost:9999/v1/leases', params={'ticker': 'ETF-Creation'})
    ### open the ETF-Redemptin lease
    resp = s.post('http://localhost:9999/v1/leases', params={'ticker': 'ETF-Redemption'})

    ### send conversion instructions (creation) to lease 1
    resp = s.post('http://localhost:9999/v1/leases/1',
                  params={'from1': 'RGLD', 'quantity1': 1000, 'from2': 'RFIN', 'quantity2': 1000})
    creation_resp = resp.json()

    currency = 10000 * 0.0375
    volume = 10000

    ### send convestion instructions (redemption) to lease 2
    resp = s.post('http://localhost:9999/v1/leases/2',
                  params={'from1': 'INDX', 'quantity1': volume, 'from2': 'CAD', 'quantity2': currency})
    creation_resp = resp.json()


def main():
    tick, status = get_tick()
    ticker_list = ['RGLD', 'RFIN', 'INDX']
    market_prices = np.array([0., 0., 0., 0., 0., 0.])
    market_prices = market_prices.reshape(3, 2)
    c_id, d_id = create_lease()
    global ORDER_LIMIT
    ORDER_LIMIT_ORG = ORDER_LIMIT

    while status == 'ACTIVE':
        volume = min(abs(get_position(index_only=True)), 125000)
        currency = volume * 0.0375
        index_pos = get_position(index_only=True)
        print(volume)
        if index_pos > 100000:
            resp = s.post(f'http://localhost:9999/v1/leases/{d_id}',
                          params={'from1': 'INDX', 'quantity1': 100000, 'from2': 'CAD', 'quantity2': 100000 * 0.0375,
                                  'id': d_id})
            print(resp.json())
        elif index_pos < -100000:
            resp = s.post(f'http://localhost:9999/v1/leases/{c_id}',
                          params={'from1': 'RGLD', 'quantity1': 100000, 'from2': 'RFIN', 'quantity2': 100000,
                                  'id': c_id})
            print(resp.json())

        for i in range(3):
            ticker_symbol = ticker_list[i]
            market_prices[i, 0], market_prices[i, 1] = get_bid_ask(ticker_symbol)

        gross_position, net_position = get_position()

        if MAX_EXPOSURE_GROSS - gross_position >= 0:
            ORDER_LIMIT = min(ORDER_LIMIT_ORG, MAX_EXPOSURE_GROSS - gross_position,
                              net_position - MAX_SHORT_EXPOSURE_NET, MAX_LONG_EXPOSURE_NET - net_position)
        else:
            ORDER_LIMIT = 0

        if gross_position < MAX_EXPOSURE_GROSS and MAX_SHORT_EXPOSURE_NET < net_position < MAX_LONG_EXPOSURE_NET:

            if market_prices[0, 0] + market_prices[1, 0] - 0.05 > market_prices[2, 1]:
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': 'RGLD', 'type': 'MARKET', 'quantity': ORDER_LIMIT,
                                      'price': market_prices[0, 1], 'action': 'SELL'})
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': 'INDX', 'type': 'MARKET', 'quantity': ORDER_LIMIT,
                                      'price': market_prices[2, 0], 'action': 'BUY'})
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': 'RFIN', 'type': 'MARKET', 'quantity': ORDER_LIMIT,
                                      'price': market_prices[1, 1], 'action': 'SELL'})
            if market_prices[0, 1] + market_prices[1, 1] < market_prices[2, 0] - 0.05:
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': 'RGLD', 'type': 'MARKET', 'quantity': ORDER_LIMIT,
                                      'price': market_prices[0, 0], 'action': 'BUY'})
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': 'INDX', 'type': 'MARKET', 'quantity': ORDER_LIMIT,
                                      'price': market_prices[2, 1], 'action': 'SELL'})
                resp = s.post('http://localhost:9999/v1/orders',
                              params={'ticker': 'RFIN', 'type': 'MARKET', 'quantity': ORDER_LIMIT,
                                      'price': market_prices[1, 0], 'action': 'BUY'})
            sleep(0.2)

        tick, status = get_tick()


if __name__ == '__main__':
    main()
