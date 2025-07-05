from ib_insync import *
import pandas as pd
from tabulate import tabulate
from colorama import Fore, Style
import time

# Połączenie z TWS – używamy readonly, by uniknąć timeout przy reqExecutions
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1, readonly=True)

# Wymuszamy rzeczywiste dane rynkowe
REALTIME_MARKET_DATA = 1
ib.reqMarketDataType(REALTIME_MARKET_DATA)

def fetch_portfolio_data(timeout=2):
    """Pobiera dane portfela w czasie rzeczywistym z konta rzeczywistego"""
    positions = ib.positions()
    data = []

    total_pnl = total_daily_pnl = 0
    total_delta = total_gamma = total_theta = total_vega = 0

    for pos in positions:
        contract = pos.contract
        position = pos.position
        avgCost = pos.avgCost

        try:
            ib.qualifyContracts(contract)
            ticker = ib.reqMktData(contract, '', False, False)
            ib.sleep(timeout)

            # Sprawdź, czy dane są rzeczywiste
            if ticker.marketDataType != REALTIME_MARKET_DATA:
                print(Fore.YELLOW + f"⚠️  Dane nie są rzeczywiste dla {contract.localSymbol} – pomijam." + Style.RESET_ALL)
                ib.cancelMktData(contract)
                continue

            currentPrice = ticker.last or ticker.close or 0
            daily_pnl = (currentPrice - (ticker.close or avgCost)) * position
            pnl = (currentPrice - avgCost) * position

            total_pnl += pnl
            total_daily_pnl += daily_pnl

            if ticker.modelGreeks:
                delta = ticker.modelGreeks.delta or 0
                gamma = ticker.modelGreeks.gamma or 0
                theta = ticker.modelGreeks.theta or 0
                vega = ticker.modelGreeks.vega or 0
            else:
                delta = gamma = theta = vega = 0

            total_delta += delta * position
            total_gamma += gamma * position
            total_theta += theta * position
            total_vega += vega * position

            data.append({
                'Symbol': contract.localSymbol,
                'Position': position,
                'Avg Cost': avgCost,
                'Current Price': currentPrice,
                'Daily P&L': daily_pnl,
                'P&L': pnl,
                'Delta': delta,
                'Gamma': gamma,
                'Theta': theta,
                'Vega': vega
            })

            ib.cancelMktData(contract)

        except Exception as e:
            print(Fore.RED + f"❌ Błąd przy {contract.localSymbol}: {e}" + Style.RESET_ALL)
            ib.cancelMktData(contract)
            continue

    return pd.DataFrame(data), {
        'Total P&L': total_pnl,
        'Total Daily P&L': total_daily_pnl,
        'Total Delta': total_delta,
        'Total Gamma': total_gamma,
        'Total Theta': total_theta,
        'Total Vega': total_vega
    }

def color_pnl(value):
    return (Fore.GREEN if value > 0 else Fore.RED) + f"{value:.2f}" + Style.RESET_ALL

try:
    while True:
        df, totals = fetch_portfolio_data(timeout=1.5)

        if not df.empty:
            df['Daily P&L (Colored)'] = df['Daily P&L'].apply(color_pnl)
            df['P&L (Colored)'] = df['P&L'].apply(color_pnl)

            print("\033c", end="")  # czyść terminal
            print(tabulate(df[['Symbol', 'Position', 'Avg Cost', 'Current Price', 'Daily P&L (Colored)', 'P&L (Colored)', 'Delta', 'Gamma', 'Theta', 'Vega']],
                           headers='keys', tablefmt='fancy_grid'))

            print("\n--- Portfolio Summary ---")
            print(f"Total Daily P&L: {color_pnl(totals['Total Daily P&L'])}")
            print(f"Total P&L: {color_pnl(totals['Total P&L'])}")
            print(f"Total Delta: {totals['Total Delta']:.2f}")
            print(f"Total Gamma: {totals['Total Gamma']:.2f}")
            print(f"Total Theta: {totals['Total Theta']:.2f}")
            print(f"Total Vega: {totals['Total Vega']:.2f}")
        else:
            print(Fore.YELLOW + "⚠️  Brak rzeczywistych danych rynkowych do wyświetlenia." + Style.RESET_ALL)

        time.sleep(5)

except KeyboardInterrupt:
    print("\n⏹️  Odświeżanie zatrzymane przez użytkownika.")
    ib.disconnect()
