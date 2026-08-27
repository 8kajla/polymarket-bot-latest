from __future__ import annotations
from config import *
from utils import *
from feeds.core import ws_status_text, LIVE_WS_STATUS
from trading.ledger import open_capital

def stats(values):
    values=[num(x) for x in values if x is not None]
    if not values:return {"count":0}
    return {"count":len(values),"average":money(sum(values)/len(values)),"minimum":money(min(values)),"maximum":money(max(values))}

def write_reports(state,feed_diag,position_diag,recon):
    open_cap=open_capital(state); closed=state["closed_trades"]
    wins=sum(1 for x in closed if num(x.get("pnl"))>0); losses=sum(1 for x in closed if num(x.get("pnl"))<0)
    summary={"version":"7.0","updated_ist":ist(),"wallet":WALLET,
      "simulator":{"max_capital":MAX_OPEN_CAPITAL,"open_capital":money(open_cap),"available_capital":money(max(0,MAX_OPEN_CAPITAL-open_cap)),
        "realized_pnl":money(state["our_realized_pnl"]),"copy_notional_fraction":COPY_NOTIONAL_FRACTION,"copied_buys":state["copied_buys"],"copied_sells":state["copied_sells"],
        "duplicates_ignored":state["duplicates_ignored"],"closed_trades":len(closed),"wins":wins,"losses":losses,
        "win_rate_pct":money(wins/len(closed)*100) if closed else 0,"skipped_capital":state["skipped_capital"],
        "skipped_liquidity":state["skipped_liquidity"],"api_errors":state["api_errors"]},
      "trader":{"realized_pnl":money(state["trader_realized_pnl"]),
        "open_positions":sum(1 for p in state["trader_positions"].values() if p["status"]=="OPEN" and p["shares"]>1e-9),
        "settled_positions":state.get("trader_settled_positions",0),
        "wins":state.get("trader_settlement_wins",0),
        "losses":state.get("trader_settlement_losses",0),
        "win_rate_pct":money(state.get("trader_settlement_wins",0)/max(1,state.get("trader_settlement_wins",0)+state.get("trader_settlement_losses",0))*100)},
      "live_feed":feed_diag,
      "sell_diagnostics":{"detected":state["sell_detected"],"processed":state["sell_processed"],
        "no_position":state["sell_rejected_no_position"],"liquidity":state["sell_rejected_liquidity"],"pending":len(state.get("pending_sells",{})),"resolution_due":state.get("resolution_due_positions",0),"resolution_redeemable_checked":state.get("resolution_redeemable_checked",0)},
      "latency":{"count":state["latency_count"],"avg_ms":state["latency_sum_ms"]/max(1,state["latency_count"]),
        "min_ms":state["latency_min_ms"],"max_ms":state["latency_max_ms"]},
      "reconciliation":recon,
      "execution":{"latency_ms":stats(state["latency_ms"]),"entry_slippage_pct":stats(state["entry_slippage_pct"]),"exit_slippage_pct":stats(state["exit_slippage_pct"])}}
    save(FILES["summary"],summary); save(FILES["trader_positions"],list(state["trader_positions"].values()))
    save(FILES["our_positions"],list(state["our_positions"].values())); save(FILES["closed_trades"],state["closed_trades"])
    save(FILES["fills"],state["fills"]); save(FILES["reconciliation"],state["reconciliation"]); save(FILES["state"],state)

def print_status(state,feed_diag,recon,force=False):
    if not force and now()-num(state.get("last_status"))<STATUS_EVERY:
        return
    state["last_status"]=now()
    open_cap=open_capital(state)
    available=max(0,MAX_OPEN_CAPITAL-open_cap)
    age=feed_diag.get("newest_age_seconds")
    feed_text=feed_diag.get("status","UNKNOWN") if age is None else f"{feed_diag.get('status','UNKNOWN')} {age:.1f}s"
    n=state["latency_count"]
    avg=state["latency_sum_ms"]/n if n else 0

    try:
        from trading.priority import stats as priority_stats
        ps=priority_stats()
    except Exception:
        ps={"queue_depth":0,"processed":0,"errors":0,"last_copy_ms":0}

    trader_w=state.get("trader_settlement_wins",0)
    trader_l=state.get("trader_settlement_losses",0)
    trader_total=trader_w+trader_l
    trader_wr=(trader_w/trader_total*100) if trader_total else 0

    print("")
    print(f"[{ist()}] STATUS | FEED {feed_text} | WS {ws_status_text()}")
    print(f"COPY  {state['copied_buys']}B/{state['copied_sells']}S | {COPY_NOTIONAL_FRACTION*100:.0f}% size | queue {ps.get('queue_depth',0)}")
    print(f"LAT   avg {avg:.0f}ms | min {state['latency_min_ms'] or 0:.0f}ms | max {state['latency_max_ms']:.0f}ms | last {ps.get('last_copy_ms',0):.0f}ms")
    print(f"CAP   open ${open_cap:.2f} | free ${available:.2f}/${MAX_OPEN_CAPITAL:.2f}")
    print(f"P&L   ours ${state['our_realized_pnl']:+.2f} | trader ${state['trader_realized_pnl']:+.2f} | trader W/L {trader_w}/{trader_l} ({trader_wr:.0f}%)")
    print(f"EXIT  settled {state['settled_positions']} | W/L {state['settlement_wins']}/{state['settlement_losses']} | pending SELL {len(state.get('pending_sells',{}))}")
    print(f"API   {state['api_requests']} req | {state['api_errors']} err | reconcile {recon.get('matches',0)} match/{recon.get('share_mismatches',0)} diff")
    if ps.get("errors") or state.get("api_errors"):
        print(f"WARN  priority errors {ps.get('errors',0)} | API errors {state.get('api_errors',0)}")
    print("-"*72)
