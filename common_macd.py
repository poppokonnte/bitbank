""" MACD共通 """
import time
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import math
import json
from pandas.core.frame import DataFrame
import bitbankcc.python_bitbankcc as bitbank
import logging
import logging.config
from _stat import filemode
import requests
from __main__ import *      # pylint: disable=wildcard-import

if __name__ == '__main__':
    ASSET_KIND = 'xym'      # テスト用
#    TEST_MODE = 1           # テスト用(売買スキップ)
    TEST_MODE = 2           # テスト用(シンボルを少々)
else:
    TEST_MODE = 0           # 通常用
    
# 通貨ペアと取引量
print( f'{ASSET_KIND=}' )
TRADE_ASSET = ASSET_KIND    # pylint: disable=undefined-variable
TRADE_PAIR = TRADE_ASSET + '_jpy'

if __name__ == '__main__':
    TRADE_PAIR_JSON = 'test_jpy'    # テスト用
else:
    TRADE_PAIR_JSON = TRADE_PAIR    # 通常用

if TEST_MODE == 2:
    TRY_BUY_STOPCOUNT = 2       # 買い注文時のリトライカウント
    TRY_SELL_STOPCOUNT = 2      # 売り注文時のリトライカウント
else:
    TRY_BUY_STOPCOUNT = 25      # 買い注文時のリトライカウント
    TRY_SELL_STOPCOUNT = 25     # 売り注文時のリトライカウント

TRY_CHECKCOUNT = 2          # 注文後のチェックカウント( 5sec * TRY_CHECKCOUNT )
ORDER_WAIT_COUNT = 1        # 瞬間的な値上がりで衝動買いしないカウント

# メイカーが－0.02％、テイカーが0.12％
COMMITION_MAKER = 0.0002
COMMITION_TAKER = 0.0012

plot_init = 0
reset_chart = 0             # 0->1で反応
reset_chart_bak = 0         # 0->1で反応
buy_price = 0
golden_hline_date = 0
dead_hline_date = 0

#####################################################
# 価格が安くても下がり始めたら売る通貨
def get_sell_asset( asset ):
    ret = 0
    if (  ( asset == "btc_jpy"  )
       or ( asset == "xrp_jpy"  )
       or ( asset == "mona_jpy" )
       or ( asset == "omg_jpy"  )
       or ( asset == "xlm_jpy"  )
       or ( asset == "xym_jpy"  )
       or ( asset == "eth_jpy"  )
       or ( asset == "bat_jpy"  )
       or ( asset == "bcc_jpy"  )
       or ( asset == "ltc_jpy"  )
       or ( asset == "qtum_jpy" )
       or ( asset == "link_jpy" )
    ):
        ret = 1
    return ret

# ロウソク足データを取得
def get_candle_data( trade_pair, candle_type, sumple_num ):

    res = pub_set.fetch_candle( trade_pair, candle_type, sumple_num )
    df_first = pd.DataFrame( res )
    #df_first = df_first.drop( columns=[ 'open', 'high', 'low', 'volume' ] )
    #df_first = df_first.rename( columns={ 'timestamp': 'date', 'close': 'buy_rate' } )
    df_first = df_first.rename( columns={ 'timestamp': 'date' } )
    for i, date in enumerate(df_first['date']):
        df_first.iloc[i, 0] = datetime.datetime.fromtimestamp( date )
    return df_first

# Lineでの通知を送信
def send_line_notify(notification_message):
    line_notify_token = get_line_token()
    line_notify_api = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': f'Bearer {line_notify_token}'}
    data = {'message': f'msg: {notification_message}'}
    requests.post(line_notify_api, headers = headers, data = data)

#履歴から価格を取得
def get_last_trade_price( asset, side ):
    ret = 0
    trade_hist = prv_set.get_trade_history( asset, 10 )
    if trade_hist == None:
        logging.info( f"---{asset} {side}----- trade_history is None. -----" )  # pylint: disable=logging-fstring-interpolation
        return float( ret )

    for val in trade_hist[ 'trades' ]:
        if val[ 'side' ] == side:
            ret = val[ 'price' ]
            break
    else:
        logging.info( f"---{asset} {side}----- trade_history is not find. -----" )  # pylint: disable=logging-fstring-interpolation
    return float( ret )

#履歴からmaker/takerを取得
def get_last_trade_MK( asset, side ):
    ret = 'maker'
    ret_base = 0
    ret_quote = 0
    trade_hist = prv_set.get_trade_history( asset, 10 )
    if trade_hist == None:
        logging.info( f"---{asset} {side}----- trade_history is None. -----" )  # pylint: disable=logging-fstring-interpolation
        return float( ret )

    for val in trade_hist[ 'trades' ]:
        if val[ 'side' ] == side:
            ret       = val[ 'maker_taker' ]
            ret_base  = float( val[ 'fee_amount_base' ] )
            ret_quote = float( val[ 'fee_amount_quote' ] )
            break
    else:
        logging.info( f"---{asset} {side}----- trade_history is not find. -----" )  # pylint: disable=logging-fstring-interpolation
    return ret, ret_base, ret_quote

#履歴から量を取得
def get_last_trade_amount( asset, side ):
    ret = 0
    trade_hist = prv_set.get_trade_history( asset, 10 )
    if trade_hist == None:
        logging.info( f"---{asset} {side}----- trade_history is None. -----" )  # pylint: disable=logging-fstring-interpolation
        return float( ret ) 

    for val in trade_hist[ 'trades' ]:
        if val[ 'side' ] == side:
            ret = val[ 'amount' ]
            break
    else:
        logging.info( f"---{asset} {side}----- trade_history is not find. -----" )  # pylint: disable=logging-fstring-interpolation

    return float( ret )

#履歴から量(直近の合計)を取得(最大10回分)
def get_last_trade_amount_sum( asset, side ):
    ret = 0
    trade_hist = prv_set.get_trade_history( asset, 10 )
    if trade_hist == None:
        logging.info( f"---{asset} {side}----- trade_history is None. -----" )  # pylint: disable=logging-fstring-interpolation
        return float( 0 ) 

    for val in trade_hist[ 'trades' ]:
        if val[ 'side' ] == side:
            ret += float( val[ 'amount' ] )
        elif ret != 0:
            break
    else:
        logging.info( f"---{asset} {side}----- trade_history is not find. -----" )  # pylint: disable=logging-fstring-interpolation

    return float( ret )

# 小数点以下指定の切り捨て
def fl_floor( num, ndigi ):
    ret = 0
    if math.isnan( num ):
        return float( ret )

    ret = num * ( 10 ** ndigi )
    ret = math.floor( ret )
    ret /= ( 10 ** ndigi )
    return float( ret )

#JPY残金リミットをファイルから取得
def get_jpy_limit():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = float( text[ TRADE_PAIR_JSON ][ "JPY_LIMIT" ] )
    if text == 0:
        text = 30000    # ファイルから取れなかった時
    return text

#EMAショートをファイルから取得 #MACDパラメータ(短期:12,長期26:,シグナル:9)
def get_short_ema_duration():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = int( text[ TRADE_PAIR_JSON ][ "SHORT_EMA_DURATION" ] )
    if text == 0:
        text = 12    # ファイルから取れなかった時
    return text

#EMAロングをファイルから取得 #MACDパラメータ(短期:12,長期26:,シグナル:9)
def get_long_ema_duration():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = int( text[ TRADE_PAIR_JSON ][ "LONG_EMA_DURATION" ] )
    if text == 0:
        text = 26    # ファイルから取れなかった時
    return text

#シグナルをファイルから取得 #MACDパラメータ(短期:12,長期26:,シグナル:9)
def get_signal_duration():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = int( text[ TRADE_PAIR_JSON ][ "SIGNAL_DURATION" ] )
    if text == 0:
        text = 9    # ファイルから取れなかった時
    return text

#アクセスキーをファイルから取得
def get_access_key( initcnt ):
    p_f = open( 'private/common_private.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    if initcnt == 0:
        return text[ "access_key" ]
    else:
        return text[ "access_key_00" + str( initcnt ) ]

#シークレットキーをファイルから取得
def get_secret_key( initcnt ):
    p_f = open( 'private/common_private.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    #return text[ "secret_key" ]
    if initcnt == 0:
        return text[ "secret_key" ]
    else:
        return text[ "secret_key_00" + str( initcnt ) ]

#Lineトークンをファイルから取得
def get_line_token():
    p_f = open( 'private/common_private.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    return text[ "line_token" ]

#ローソク足タイプをファイルから取得 #"1m":"5m":"15m":"30m":"1h":"4h":"8h":"12h":"1d":"1w"
def get_candle_type():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = text[ TRADE_PAIR_JSON ][ "CANDLE_TYPE" ]
    return text

#インターバルタイマをファイルから取得
def get_interval_sec():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = int( text[ TRADE_PAIR_JSON ][ "INTERVAL_SEC" ] )
    if text == 0:
        text = 60    # ファイルから取れなかった時
    epoc = text
    return epoc

#buy_price取得
def get_buy_price():
    p_f = open( '_compara.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    return float( text[ TRADE_PAIR_JSON ][ "buy_price" ] )

#最小価格刻みを取得
def get_min_unit_price():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    return float( text[ TRADE_PAIR_JSON ][ "MIN_PRICE" ] )

#画面表示フラグをファイルから取得
def get_disp_chart():
    return 0
#    p_f = open( '_common.json', 'r' )
#    text = json.load( p_f )
#    p_f.close()
#    return int( text[ TRADE_PAIR_JSON ][ "disp_chart" ] )

#画面表示フラグをファイルから取得
def get_reset_chart():
    return 0
#    p_f = open( '_common.json', 'r' )
#    text = json.load( p_f )
#    p_f.close()
#    return int( text[ TRADE_PAIR_JSON ][ "reset_chart" ] )

#取引量(金額)をファイルから取得
def get_trade_price():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = float( text[ TRADE_PAIR_JSON ][ "TRADE_PRICE" ] )
    if text == 0:
        text = 20000    # ファイルから取れなかった時
    return text

#取引量をファイルから取得
def get_trade_amount():
    p_f = open( '_common.json', 'r' )
    text = json.load( p_f )
    p_f.close()
    text = float( text[ TRADE_PAIR_JSON ][ "TRADE_AMOUNT" ] )
    
    trade_price = get_trade_price()
    free_jpy = get_free_amount( 'jpy' )
    if trade_price != 0:
        if trade_price > free_jpy:
            trade_price = free_jpy * 0.95
        text = fl_floor( trade_price / float( BitBankPubAPI().get_ticker( TRADE_PAIR )['buy'] ), 4 )   # 小数点4桁が限界？
    if text == 0:
        text = 0    # ファイルから取れなかった時
    return text

#利用可能な量を取得
def get_free_amount( asset ):
    ret = 0
    ast = prv_set.get_asset()
    for val in ast['assets']:
        if val['asset'] == asset:
            ret = val['free_amount']
            break
    return float( ret )

#買い注文
def orderbuy():

    ret = None
    stopcount = 0
    preamount = 0
    orderamount = 0
    buyamount = get_trade_amount()      # 金額設定から、基本取引量取得
    unit_min_price = get_min_unit_price()         # 最小価格刻みを取得

    if TEST_MODE == 1:
        print( "orderbuyをスキップしました。" )
        return ret
    if TEST_MODE == 2:
        buyamount = 2

    while True:
        ticker_val = pub_set.get_ticker( TRADE_PAIR )
        lastp = float(ticker_val['last'])
        sellp = float(ticker_val['sell'])
        buyp = float(ticker_val['buy'])
        free_amount = get_free_amount( TRADE_ASSET )
        # 目標分だけ買えたら抜け
        if free_amount >= buyamount:
            logging.info( f"[{TRADE_PAIR}] free_amount = {free_amount}" )   # pylint: disable=logging-fstring-interpolation
            return ret

        # 注文する量を計算( 目標の量 - 保有量 )
        orderamount = buyamount - free_amount
        preamount = orderamount
        orderamount = fl_floor( orderamount, 4 )
        buyamount = buyamount - abs(preamount - orderamount)    # 小数点切り捨て分、量が合わないかもなので、購入量を少し引き下げ

        # 買い注文のパラメータ決定
        amount = orderamount
        side = 'buy'
        if stopcount < TRY_BUY_STOPCOUNT:
            if ( buyp + unit_min_price) <= ( sellp - unit_min_price ):    # 注文価格の最大値チェック
                price = buyp + unit_min_price                        # 注文可能な価格であれば、少し高くして買い注文
            else:
                price = buyp
            order_type = 'limit'
            post_only = True
        else:
            price = sellp
            amount = fl_floor( amount * 0.9, 4 )
            order_type = 'market'
            post_only = False
            send_line_notify( f"$$$$$$ {TRADE_PAIR} [order buy]({stopcount}) {price=} {amount=} {order_type=} last={lastp} sell={sellp} buy={buyp} order amount={orderamount}" )
            
        # 買い注文実行
        logging.info( f"$$$$$$ {TRADE_PAIR} [order buy]({stopcount}) {price=} {amount=} {order_type=} last={lastp} sell={sellp} buy={buyp} order amount={orderamount}" )    # pylint: disable=logging-fstring-interpolation
        ret = prv_set.order( TRADE_PAIR, price, amount, side, order_type, post_only )

        # 注文後のステータス変化待ち
        if order_type == 'market':  # 成行注文の場合はorderしたら抜け
            logging.info( f"--- {TRADE_PAIR} after order buy({stopcount}) {order_type=} price={price}*{amount} = {price * amount}" )   # pylint: disable=logging-fstring-interpolation
            time.sleep(1)
            return ret
        if ret == None:             # 注文が失敗していたら最初からやり直し
            time.sleep(5)
            continue

        logging.info( f"--- {TRADE_PAIR} after order buy({stopcount}) order_id={ret['order_id']} price={price}*{amount} = {price * amount}" )   # pylint: disable=logging-fstring-interpolation
        for i in range( TRY_CHECKCOUNT ):
            time.sleep(5)
            ret2 = prv_set.get_order( TRADE_PAIR, ret['order_id'] )
            if ret2 == None:        # 注文が失敗していたら抜け
                stopcount = 0
                break
            if ret2['status'] != "UNFILLED":    # 注文が"未約定"以外の状態になったら抜け
                #time.sleep(3)
                fillamount = get_last_trade_amount( TRADE_PAIR, 'buy' )
                logging.info( f"--- {TRADE_PAIR} order check A({stopcount})[{i}] status[{ret2['status']}] filled price={ret2['price']} amount={fillamount}" )  # pylint: disable=logging-fstring-interpolation
                break
        
        # 注文後のステータス判定
        if ( ret2 == None ):                                    # 注文失敗
            logging.info( f"--- {TRADE_PAIR} order check B({stopcount}) ret2 == None" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "CANCELED_UNFILLED" ):         # 取消済
            logging.info( f"--- {TRADE_PAIR} order check C({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "CANCELED_PARTIALLY_FILLED" ): # 取消済(一部約定)
            logging.info( f"--- {TRADE_PAIR} order check D({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "PARTIALLY_FILLED" ):          # 注文中(一部約定)
            logging.info( f"--- {TRADE_PAIR} order check E({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
            prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
            logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )
        elif ( ret2['status'] == "UNFILLED" ):                  # 注文中 約定せず(キャンセルしてやり直し)
            logging.info( f"--- {TRADE_PAIR} order check F({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
            prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
            logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )
        else:          # その他、FULLY_FILLED 約定済み とかはとりあえずスルー
            logging.info( f"--- {TRADE_PAIR} order check G({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        stopcount += 1

#売り注文(指値、成行)
def ordersell():

    ret = None
    stopcount = 0
    unit_min_price = get_min_unit_price()         # 最小価格刻みを取得

    if TEST_MODE == 1:
        print( "ordersellをスキップしました。" )
        return ret

    while True:
        ticker_val = pub_set.get_ticker( TRADE_PAIR )
        lastp = float(ticker_val['last'])
        sellp = float(ticker_val['sell'])
        buyp = float(ticker_val['buy'])
        free_amount = get_free_amount( TRADE_ASSET )
        # 持っている分が全て売れたら抜け
        if free_amount == 0:
            logging.info( f"[{TRADE_PAIR}] ammount = 0 sold out ?" )    # pylint: disable=logging-fstring-interpolation
            return ret

        # 売り注文のパラメータ決定
        amount = free_amount
        side = 'sell'
        if stopcount < TRY_SELL_STOPCOUNT:
            if ( buyp + unit_min_price) <= ( sellp - unit_min_price ):    # 注文価格の最大値チェック
                price = sellp - unit_min_price                       # 注文可能な価格であれば、少し高くして買い注文
            else:
                price = sellp
            order_type = 'limit'
            post_only = True
        else:
            price = buyp
            order_type = 'market'
            post_only = False
            send_line_notify( f"$$$$$$ {TRADE_PAIR} [order sell]({stopcount}) {price=} {amount=} {order_type=} last={lastp} sell={sellp} buy={buyp} amount={free_amount}" )

        # 売り注文実行
        logging.info( f"$$$$$$ {TRADE_PAIR} [order sell]({stopcount}) {price=} {amount=} {order_type=} last={lastp} sell={sellp} buy={buyp} amount={free_amount}" ) # pylint: disable=logging-fstring-interpolation
        ret = prv_set.order( TRADE_PAIR, price, amount, side, order_type, post_only )
        
        # 注文後のステータス変化待ち
        if order_type == 'market':  # 成行注文の場合はorderしたら抜け
            logging.info( f"--- {TRADE_PAIR} after order sell({stopcount}) {order_type=} price={price}*{amount} = {price * amount}" )   # pylint: disable=logging-fstring-interpolation
            time.sleep(1)
            break
        if ret == None:             # 注文が失敗していたら最初からやり直し
            time.sleep(5)
            continue

        logging.info( f"--- {TRADE_PAIR} after order sell({stopcount}) order_id={ret['order_id']} price={price}*{amount} = {price * amount}" )  # pylint: disable=logging-fstring-interpolation
        for i in range( TRY_CHECKCOUNT ):
            time.sleep(5)
            ret2 = prv_set.get_order( TRADE_PAIR, ret['order_id'] )
            if ret2 == None:    # 注文が失敗していたら抜け
                stopcount = 0
                break
            if ret2['status'] != "UNFILLED":    # 注文が"未約定"以外の状態になったら抜け
                #time.sleep(5)
                fillamount = get_last_trade_amount( TRADE_PAIR, 'sell' )
                logging.info( f"--- {TRADE_PAIR} order check[{i}] status[{ret2['status']}] filled price={ret2['price']} amount={fillamount}" )  # pylint: disable=logging-fstring-interpolation
                break

        # 注文後のステータス判定
        if ( ret2 == None ):                                    # 注文失敗
            logging.info( f"--- {TRADE_PAIR} order check B({stopcount}) ret2 == None" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "CANCELED_UNFILLED" ):         # 取消済
            logging.info( f"--- {TRADE_PAIR} order check C({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "CANCELED_PARTIALLY_FILLED" ): # 取消済(一部約定)
            logging.info( f"--- {TRADE_PAIR} order check D({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "PARTIALLY_FILLED" ):          # 注文中(一部約定)
            logging.info( f"--- {TRADE_PAIR} order check E({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
            prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
            logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )
        elif ( ret2['status'] == "UNFILLED" ):                  # 注文中 約定せず(キャンセルしてやり直し)
            logging.info( f"--- {TRADE_PAIR} order check F({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
            prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
            logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )
        else:          # その他、FULLY_FILLED 約定済み とかはとりあえずスルー
            logging.info( f"--- {TRADE_PAIR} order check G({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        stopcount += 1

############################################################################################
# 逆指値情報クラス
############################################################################################
class StopOrderInfo:
    def __init__( self ):
        self.order_id = 0
        self.stop_limit = 0

#売り注文(逆指値、逆指値成行)
def stop_order( df ):

    ret = None
    stopcount = 0
    unit_min_price = get_min_unit_price()         # 最小価格刻みを取得

    df[ 'fluc' ] = df[ 'close' ] - df[ 'open' ]    
    now_open  = df[ 'open' ].iloc[-1]
    now_high  = df[ 'high' ].iloc[-1]
    now_low   = df[ 'low' ].iloc[-1]
    now_close = df[ 'close' ].iloc[-1]
    before_open  = df[ 'open' ].iloc[-2]
    before_high  = df[ 'high' ].iloc[-2]
    before_low   = df[ 'low' ].iloc[-2]
    before_close = df[ 'close' ].iloc[-2]

    for i in range(-1,-10,-1):
        #if df[ 'fluc' ].iloc[i] > 0:   # 一つ前が陽線の場合
        print( f"[{i}] open:{df[ 'open' ].iloc[i]:.3f} high:{df[ 'high' ].iloc[i]:.3f} low:{df[ 'low' ].iloc[i]:.3f} close:{df[ 'close' ].iloc[i]:.3f} fluc:{df[ 'fluc' ].iloc[i]:.3f} 変動率:{fl_floor(df[ 'fluc' ].iloc[i] / df[ 'open' ].iloc[i] * 100, 3)}%" )


    return ret

    while True:
        ticker_val = pub_set.get_ticker( TRADE_PAIR )
        lastp = float(ticker_val['last'])
        sellp = float(ticker_val['sell'])
        buyp = float(ticker_val['buy'])
        free_amount = get_free_amount( TRADE_ASSET )
        # 持っている分が全て売れたら抜け
        if free_amount == 0:
            logging.info( f"[{TRADE_PAIR}] ammount = 0 sold out ?" )    # pylint: disable=logging-fstring-interpolation
            return 0

        # 売り注文のパラメータ決定
        amount = free_amount
        side = 'sell'
        if stopcount < TRY_SELL_STOPCOUNT:
            price = sellp - min_price
            order_type = 'stop_limit'
            post_only = True
            trigger_price = 0
        else:
            price = buyp
            order_type = 'stop'
            post_only = False
            trigger_price = 0
        
        logging.info( f"$$$$$$ {TRADE_PAIR} [order sell]({stopcount}) {price=} {amount=} {order_type=} last={lastp} sell={sellp} buy={buyp} amount={free_amount}" ) # pylint: disable=logging-fstring-interpolation
        ret = prv_set.order( TRADE_PAIR, price, amount, side, order_type, post_only )
        if order_type == 'market':  # 成行注文の場合はorderしたら抜け
            logging.info( f"--- {TRADE_PAIR} after order sell({stopcount}) {order_type=} price={price}*{amount} = {price * amount}" )   # pylint: disable=logging-fstring-interpolation
            time.sleep(1)
            break
        if ret == None:             # 注文が失敗していたら最初からやり直し
            time.sleep(5)
            continue
        logging.info( f"--- {TRADE_PAIR} after order sell({stopcount}) order_id={ret['order_id']} price={price}*{amount} = {price * amount}" )  # pylint: disable=logging-fstring-interpolation
        for i in range( TRY_CHECKCOUNT ):
            time.sleep(5)
            ret2 = prv_set.get_order( TRADE_PAIR, ret['order_id'] )
            if ret2 == None:    # 注文が失敗していたら抜け
                stopcount = 0
                break
            if ret2['status'] != "UNFILLED":    # 注文が"未約定"以外の状態になったら抜け
                #time.sleep(5)
                fillamount = get_last_trade_amount( TRADE_PAIR, 'sell' )
                logging.info( f"--- {TRADE_PAIR} order check[{i}] status[{ret2['status']}] filled price={ret2['price']} amount={fillamount}" )  # pylint: disable=logging-fstring-interpolation
                break
        
        # 注文後のステータス判定
        if ( ret2 == None ):                                    # 注文失敗
            logging.info( f"--- {TRADE_PAIR} order check B({stopcount}) ret2 == None" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "CANCELED_UNFILLED" ):         # 取消済
            logging.info( f"--- {TRADE_PAIR} order check C({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "CANCELED_PARTIALLY_FILLED" ): # 取消済(一部約定)
            logging.info( f"--- {TRADE_PAIR} order check D({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        elif ( ret2['status'] == "PARTIALLY_FILLED" ):          # 注文中(一部約定)
            logging.info( f"--- {TRADE_PAIR} order check E({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
            prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
            logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )
        elif ( ret2['status'] == "UNFILLED" ):                  # 注文中 約定せず(キャンセルしてやり直し)
            logging.info( f"--- {TRADE_PAIR} order check F({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
            prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
            logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )
        else:          # その他、FULLY_FILLED 約定済み とかはとりあえずスルー
            logging.info( f"--- {TRADE_PAIR} order check G({stopcount}) status[{ret2['status']}]" )   # pylint: disable=logging-fstring-interpolation
        stopcount += 1
        """
        # 注文失敗 or 約定済み
        if ( ret2 == None ) or ( ret2['status'] == "FULLY_FILLED" ):
            logging.info( f"--- {TRADE_PAIR} order check({stopcount})" )   # pylint: disable=logging-fstring-interpolation
        # 約定せず or 部分約定 (キャンセルしてやり直し)
        else:
            if ret2['status'] != "CANCELED_UNFILLED":
                prv_set.cancel_order( TRADE_PAIR, ret['order_id'] )
                logging.info( f"--- {TRADE_PAIR} order cancel({stopcount})" )   # pylint: disable=logging-fstring-interpolation
            else:
                logging.info( f"--- {TRADE_PAIR} order retry({stopcount})" )   # pylint: disable=logging-fstring-interpolation
        stopcount += 1
        """

############################################################################################
# ビットバンク Public API
############################################################################################
class BitBankPubAPI:

    def __init__(self):
        self.pub = bitbank.public()

    def get_ticker(self, pair): #[Public API] ティッカー情報を取得。
        for i in range(3):  # 最大3回実行
            try:
                value = self.pub.get_ticker(pair)
                return value
            except Exception as e:  # pylint: disable=broad-except
                send_line_notify( f"get_ticker(){TRADE_PAIR}例外発生；{e} [{i + 1}]回目" )
                logging.info( e )
                time.sleep( ( i + 1 ) * 10 )
        else:
            send_line_notify( f"get_ticker(){TRADE_PAIR}例外発生；[全て失敗しました。]" )
            logging.info( e )
            return None

    def get_tickers(self):  #[Public API] 全ペアのティッカー情報を取得。
        try:
            value = self.pub.get_tickers()
            return value
        except Exception as e:  # pylint: disable=broad-except
            send_line_notify( f"get_tickers(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return None

    def get_tickers_jpy(self):  #[Public API] JPYペアのティッカー情報を取得。
        try:
            value = self.pub.get_tickers_jpy()
            return value
        except Exception as e:  # pylint: disable=broad-except
            send_line_notify( f"get_tickers_jpy(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return None

    def get_depth(self, pair):  #[Public API] 板情報を取得。
        try:
            value = self.pub.get_depth(pair)
            return value
        except Exception as e:  # pylint: disable=broad-except
            send_line_notify( f"get_depth(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return None

    def get_transactions(self, pair, yyyymmdd=None):    #[Public API] 指定された日付の全約定履歴を取得。
        try:
            value = self.pub.get_transactions(pair, yyyymmdd)
            return value
        except Exception as e:  # pylint: disable=broad-except
            send_line_notify( f"get_transactions(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return None

    def get_candlestick(self, pair, candle_type, yyyymmdd): #[Public API] 指定された日付のロウソク足データを取得。
        try:
            value = self.pub.get_candlestick(pair, candle_type, yyyymmdd)
            return value
        except Exception as e:
            send_line_notify( f"get_candlestick(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return None

    def fetch_candle(self, pair, candle_type, count): #[Public API] 指定された数のロウソク足データを取得。
        for i in range(3):  # 最大3回実行
            try:
                value = self.pub.fetch_candle(pair, candle_type, count)
                return value
            except Exception as e:
                send_line_notify( f"fetch_candle(){TRADE_PAIR}例外発生；{e} [{i + 1}]回目" )
                logging.info( e )
                time.sleep( ( i + 1 ) * 10 )
        else:
            send_line_notify( f"fetch_candle(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return None

    def get_bitbank_str(self, base):    #[Public API] Input:1m,5m,15m,30m,1h,4h,8h,12h,1d,1w Output:1min,5min,,,
        #Output: 1min, 5min, 15min, 30min, 1hour, 4hour, 8hour, 12hour, 1day, 1week, 1month
        try:
            value = self.pub.get_bitbank_str( base )
            return value
        except Exception as e:
            send_line_notify( f"get_bitbank_str(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return '1hour'
    
    def get_floor_str(self, base):      #[Public API] Input:1m,5m,15m,30m,1h,4h,8h,12h,1d,1w Output:1T,5T,,,
        try:
            value = self.pub.get_floor_str( base )
            return value
        except Exception as e:
            send_line_notify( f"get_floor_str(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return '1H'

    def get_candle_epoc(self): #[Public API] Input:5s,10s,15s,30s,1m,2m,3m,5m,10m,15m,30m,1h,2h,3h,4h,6h,8h,12h,1d Output:5,10,,,
        try:
            value = self.pub.get_candle_epoc( get_candle_type() )
            return value
        except Exception as e:
            send_line_notify( f"get_candle_epoc(){TRADE_PAIR}例外発生；{e}" )
            logging.info( e )
            return 0

############################################################################################
# ビットバンク Private API
############################################################################################
class BitBankPrvAPI:
    initcnt = 0

    def __call__(self):
        BitBankPrvAPI.initcnt += 1
        if BitBankPrvAPI.initcnt == 3:
            BitBankPrvAPI.initcnt = 0

    def __init__(self):
        API_KEY = get_access_key(BitBankPrvAPI.initcnt)
        API_SECRET = get_secret_key(BitBankPrvAPI.initcnt)
        self.prv = bitbank.private(API_KEY, API_SECRET)

    def get_asset(self):
        for i in range(3):  # 最大3回実行
            try:
                value = self.prv.get_asset()
                return value
            except Exception as e:
                send_line_notify( f"get_asset(){TRADE_PAIR}例外発生；{e} [{i + 1}]回目" )
                logging.info( f'{e} [{i + 1}]回目' )
                time.sleep( ( i + 1 ) * 10 )
        else:
            send_line_notify( f"get_asset(){TRADE_PAIR}例外発生；[全て失敗しました。]" )
            logging.info( f'[全て失敗しました。]' )
            return None

    def order(self, pair, price, amount, side, order_type, post_only ):
        for i in range(3):  # 最大3回実行
            try:
                value = self.prv.order(pair, price, amount - ( amount * 0.1 * i ), side, order_type, post_only )
                return value
            except Exception as e:
                send_line_notify( f"order(){TRADE_PAIR}例外発生；{e} {price=},{amount - (amount * 0.1 * i)},{side=},{order_type=},{post_only=} [{i + 1}]回目" )
                logging.info( f'{e} {price=},{amount - (amount * 0.1 * i)},{side=},{order_type=},{post_only=} [{i + 1}]回目' )
                time.sleep( ( i + 1 ) * 10 )
        else:
            #send_line_notify( f"order(){TRADE_PAIR}例外発生；{e} {price=},{amount=},{side=},{order_type=},{post_only=} [全て失敗しました。]" )
            #logging.info( f'[全て失敗しました。]' )
            send_line_notify( f"order(){TRADE_PAIR}例外発生 [全て失敗しました。]" )
            logging.info( f'[全て失敗しました。]' )
            return None

    def get_order(self, pair, order_id):
        for i in range(3):  # 最大3回実行
            try:
                value = self.prv.get_order(pair, order_id )
                return value
            except Exception as e:
                send_line_notify( f"get_order(){TRADE_PAIR}例外発生；{e}" )
                logging.info( e )
                time.sleep( ( i + 1 ) * 10 )
        else:
            send_line_notify( f"get_order(){TRADE_PAIR}例外発生；[全て失敗しました。]" )
            logging.info( f'[全て失敗しました。]' )
            return None
    
    def cancel_order(self, pair, order_id):
        for i in range(3):  # 最大3回実行
            try:
                value = self.prv.cancel_order(pair, order_id )
            except Exception as e:
                send_line_notify( f"cancel_order(){TRADE_PAIR}例外発生；{e}" )
                logging.info( e )
                time.sleep( ( i + 1 ) * 10 )
            else:
                return value
        send_line_notify( f"cancel_order()例外発生[全て失敗しました。]" )
        logging.info( f"[全て失敗しました。]" )
        return None

    def get_trade_history(self, pair, order_count): #約定履歴を取得する
        for i in range(3):  # 最大3回実行
            try:
                value = self.prv.get_trade_history(pair, order_count )
                return value
            except Exception as e:
                send_line_notify( f"get_trade_history(){TRADE_PAIR}例外発生；{e}" )
                logging.info( e )
                time.sleep( ( i + 1 ) * 10 )
        else:
            send_line_notify( f"get_trade_history(){TRADE_PAIR}例外発生；[全て失敗しました。]" )
            logging.info( f'[全て失敗しました。]' )
            return None

############################################################################################
# メイン処理
############################################################################################

# ログ設定
MYFORMAT='[%(asctime)s]%(filename)s(%(lineno)d): %(message)s'
logging.basicConfig(
    filename='log/'+TRADE_PAIR_JSON+'.log',
    filemode='w', # Default is 'a'
    format=MYFORMAT,
    datefmt='%Y-%m-%d %H:%M:%S', 
    level=logging.INFO)
console = logging.StreamHandler()
logging.getLogger('').addHandler(console)

# ビットバンククラスインスタンス取得、初期化
pub_set = BitBankPubAPI()
prv_set = BitBankPrvAPI()

candle_update = 0
ordering = 0
order_wait_count = 0
total_buy = 0
total_sell = 0
lastdate = pd.DataFrame( [ datetime.datetime(2000, 1, 1, 0, 0, 0) ], columns = [ 'date' ] )
lastdate = lastdate['date'].dt.floor( pub_set.get_floor_str( get_candle_type() ) )

# 買い価格更新
buy_price = get_buy_price()
logging.info( f"last buy_price = {buy_price}" )
free_amount = get_free_amount( TRADE_ASSET )
logging.info( f"free_amount = {free_amount}" )
if free_amount != 0:
    if buy_price == 0:
        buy_price = get_last_trade_price( TRADE_PAIR , 'buy' )

while True:

    # ロウソク足の間隔毎にロウソク足データを取得＆更新
    if lastdate[0] + datetime.timedelta( seconds = pub_set.get_candle_epoc() ) <= datetime.datetime.now():
        df = get_candle_data( TRADE_PAIR, get_candle_type(), get_long_ema_duration() * 2 + 1 )
        lastdate = pd.DataFrame( [ datetime.datetime.now() ], columns = [ 'date' ] )
        lastdate = lastdate['date'].dt.floor( pub_set.get_floor_str( get_candle_type() ) )
        candle_update = 1      # ローソク足データ更新回
        ordering = 0

    ticker = pub_set.get_ticker( TRADE_PAIR )
    #buy_now = float(ticker['buy'])
    buy_now = float(ticker['last'])
    sell_now = float(ticker['sell'])
    #last_price = float(ticker['last'])
    date_now = datetime.datetime.now().replace(microsecond = 0)
    
    df_new = pd.DataFrame( [ (buy_now, sell_now, date_now ) ], columns = [ 'close' , 'sell_rate', 'date' ] )
    if candle_update != 1:              # キャンドルアップデート回で無ければ
        df = df.drop(df.index[-1])      # 最終行を削除して更新
    df = df.append( df_new , ignore_index = True )

    # MACDの計算を行う
    df[ 'ema_short' ] = df[ 'close' ].ewm( span = get_short_ema_duration() ).mean()
    df[ 'ema_long' ] = df[ 'close' ].ewm( span = get_long_ema_duration() ).mean()
    df[ 'macd' ] = df[ 'ema_short' ] - df[ 'ema_long' ]
    df[ 'signal' ] = df[ 'macd' ].ewm( span = get_signal_duration() ).mean()

    if TEST_MODE == 1:
        stop_order( df )

    #ゴールデンクロス
    if (( df[ 'macd' ].iloc[-1] > df[ 'signal' ].iloc[-1] ) and ( df[ 'macd' ].iloc[-2] < df[ 'signal' ].iloc[-2] )) or ( TEST_MODE == 2 ):
        logging.info( f"{TRADE_PAIR} (golden cross)" )
        order_wait_count += 1
        golden_hline_date = df[ 'date' ].iloc[-1]
        if buy_price == 0:
            #JPY残金確認
            if get_free_amount( 'jpy' ) > get_jpy_limit():
                #注文中判断
                if True:    #ordering == 0:      #注文中判定ヤメ
                    logging.info( f"------ GC order check ==> order_wait_count({order_wait_count}/{ORDER_WAIT_COUNT})" )
                    if order_wait_count >= ORDER_WAIT_COUNT:
                        ordering = 1
                        res_buy = orderbuy()
                        # 履歴から取った買い価格で更新
                        hist_price = get_last_trade_price( TRADE_PAIR , 'buy' )
                        if hist_price != 0:
                            buy_price = hist_price
                        else:
                            buy_price = buy_now   # 履歴から買い価格が取れなかったら、板の買い価格をセットしておく
                        hist_amount = get_last_trade_amount_sum( TRADE_PAIR , 'buy' )
                        ret_mk, ret_base, ret_quota = get_last_trade_MK( TRADE_PAIR , 'buy' )
                        if ret_mk == 'maker':
                            total_buy = buy_price * hist_amount - ret_base - ret_quota
                        else:
                            total_buy = buy_price * hist_amount + ret_base + ret_quota
                        logging.info( f"[{TRADE_ASSET} buy]：レート約[{buy_price}]×量[{hist_amount}]\n＝合計[{total_buy}]円 買いました。" )
                        send_line_notify( f"[{TRADE_ASSET} buy]：レート約[{buy_price}]×量[{hist_amount}]\n＝合計[{total_buy}]円 買いました。" )
                        #stop_order( df )
                else:
                    order_wait_count = 0
                    logging.info( f"------ GC through ==> order during: golden_hline {golden_hline}" )
            else:
                logging.info( f"------ GC through ==> no JPY left:{get_free_amount( 'jpy' )}" )
        else:
            logging.info( f"------ GC through ==> remain buy_price:{buy_price}" )
    #デッドクロス
    #elif ( df[ 'macd' ].iloc[-1] <= df[ 'signal' ].iloc[-1] ) and ( df[ 'macd' ].iloc[-2] > df[ 'signal' ].iloc[-2] ):
    #macdの傾きがマイナスだったらデッドクロス前に売り
    elif ( buy_price != 0 ) and ( df[ 'macd' ].iloc[-2] > df[ 'macd' ].iloc[-1] ):
        logging.info( f"{TRADE_PAIR} (pre dead cross) {df[ 'macd' ].iloc[-2]} > {df[ 'macd' ].iloc[-1]}" )
        order_wait_count = 0
        dead_hline_date = df[ 'date' ].iloc[-1]
        if buy_price != 0:
            #注文中の区間で、すぐ下がりそうだったら値段を見ずに売り判断
            if ( ( ordering == 1 )                      # 注文中の区間 
              or ( get_sell_asset( TRADE_PAIR ) == 1 )  # 価格が安くても下がり始めたら売る通貨
              or ( sell_now > buy_price ) ):            # 価格チェック
            #逆に、注文中の区間は、逆に様子見(すぐには売らない、上昇トレンドの時はこっちかな？)
            #if ( ordering != 1 ) and ( ( get_sell_asset( TRADE_PAIR ) == 1 ) or ( sell_now > buy_price ) ):
                logging.info( f"------ DC force sell:[{ordering}] sell_now: {sell_now} buy_price: {buy_price}" )
                res_sell = ordersell()
                hist_price = get_last_trade_price( TRADE_PAIR , 'sell' )
                hist_amount = get_last_trade_amount_sum( TRADE_PAIR , 'sell' )
                ret_mk, ret_base, ret_quota = get_last_trade_MK( TRADE_PAIR , 'sell' )
                if ret_mk == 'maker':
                    total_sell = hist_price * hist_amount + ret_base + ret_quota
                else:
                    total_sell = hist_price * hist_amount - ret_base - ret_quota
                logging.info(     f"[{TRADE_ASSET} sell]：Rate[{hist_price}]({buy_price})×[{hist_amount}]\n＝計[{total_sell}]円売りました。\n$${total_sell-total_buy}$$" )
                send_line_notify( f"[{TRADE_ASSET} sell]：Rate[{hist_price}]({buy_price})×[{hist_amount}]\n＝計[{total_sell}]円売りました。\n$${total_sell-total_buy}$$" )
                ordering = 0
                buy_price = 0
            else:
                logging.info( f"------ DC through ==> sell_now: {sell_now} buy_price: {buy_price}" )
            '''
            if sell_now > buy_price:
                #注文中判断
                if order_during == 0:
                    res_sell = ordersell()
                    order_during = 1
                    buy_price = 0
                    hist = get_last_trade_price( TRADE_PAIR , 'sell' )
                    time.sleep( 5 )
                    hist_amount = get_last_trade_amount_sum( TRADE_PAIR , 'sell' )
                    send_line_notify( f"[{TRADE_ASSET} sell]：レート約[{hist}]×量[{hist_amount}]\n＝合計[{hist*hist_amount}]円 売りました。" )
                else:
                    logging.info( f"------ DC through ==> order during: dead_hline {dead_hline}" )
            else:
                logging.info( f"------ DC through ==> sell_now: {sell_now} buy_price: {buy_price}" )
            '''
        else:
            logging.info( f"------ DC through ==> buy_price:0 {buy_price}" )
    #クロス無し
    else:
        order_wait_count = 0
        logging.info( f"--- {TRADE_PAIR} none---: buy_now={buy_now} sell_now={sell_now}" )

    #エクセルに結果保存
    #df.to_excel( TRADE_PAIR + '.xlsx', sheet_name=TRADE_PAIR, index=False )
    #TSVに結果保存
    df.to_csv( 'log/' + TRADE_PAIR + '.tsv', sep='\t' )

    #価格をプロッティング
    if get_disp_chart() == 1:
        reset_chart_bak = reset_chart
        reset_chart = get_reset_chart()
        if ( plot_init == 0 ) or ( reset_chart_bak == 0 and reset_chart == 1 ) :
            plot_init = 1
            buy_rate_min = df[ 'close' ].min()
            buy_rate_max = df[ 'close' ].max()
            macd_min = df[ 'macd' ].min()
            macd_max = df[ 'macd' ].max()
            fig, (ax1, ax2) = plt.subplots(2,1, gridspec_kw = { 'height_ratios':[1, 1]} )
            line1, = ax1.plot( df[ 'date' ], df[ 'close' ], color='blue' )
            #line2, = ax1.plot( df[ 'date' ], df[ 'sell_rate' ], color='cyan' )
            line3, = ax2.plot( df[ 'date' ], df[ 'macd' ], color='blue' )
            line4, = ax2.plot( df[ 'date' ], df[ 'signal' ], color='magenta' )
            ax1.set_title( TRADE_PAIR )
            fig.tight_layout()
        else:
            if buy_rate_min > df[ 'close' ].min():
                buy_rate_min = df[ 'close' ].min()
            if buy_rate_max < df[ 'close' ].max():
                buy_rate_max = df[ 'close' ].max()
            if macd_min > df[ 'macd' ].min():
                macd_min = df[ 'macd' ].min()
            if macd_max < df[ 'macd' ].max():
                macd_max = df[ 'macd' ].max()

            line1.set_data( df[ 'date' ], df[ 'close' ] )
            #line2.set_data( df[ 'date' ], df[ 'sell_rate' ] )
            line3.set_data( df[ 'date' ], df[ 'macd' ] )
            line4.set_data( df[ 'date' ], df[ 'signal' ] )
            ax1.set_xlim( df[ 'date' ].min(), df[ 'date' ].max() )
            ax1.set_ylim( buy_rate_min - ( ( buy_rate_max - buy_rate_min ) * 0.1 ), buy_rate_max + ( ( buy_rate_max - buy_rate_min ) * 0.1 ) )
            ax2.set_xlim( df[ 'date' ].min(), df[ 'date' ].max() )
            ax2.set_ylim( macd_min - ( ( macd_max - macd_min ) * 0.1 ), macd_max + ( ( macd_max - macd_min ) * 0.1 ) )
            if golden_hline_date != 0:
                ax2.vlines( golden_hline_date, macd_min, macd_max, colors='orange' )
            if dead_hline_date != 0:
                ax2.vlines( dead_hline_date, macd_min, macd_max, colors='red' )
        plt.pause( get_interval_sec() )
    else:
        time.sleep( get_interval_sec() )
    
    # 後処理
    candle_update = 0

