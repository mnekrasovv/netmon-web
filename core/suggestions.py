"""Smart suggestions engine: rule-based analysis of test results."""

from __future__ import annotations


def analyze(results: dict) -> list:
    """
    Analyze a bag of test results and return a list of suggestions.

    Input shape (any subset present is OK):
    {
        "ping": [{host, name, avg, loss, ok, sent, recv}, ...],
        "gateway_ping": {avg, loss, ok},
        "dns_matrix": {results: {domain: {server: ip}}},
        "trace": [{hop, ip, avg_rtt, timeout, ...}, ...],
        "mtr": [...],
        "http": [{url, ok, status, time_ms, error}, ...],
        "external_ip": {geo: {...}, services: {...}},
        "batch": {ok, slow, warn, fail, total, results: [...]},
    }

    Output: [{level: "info"|"warn"|"error", title, body}, ...]
    """
    suggestions = []

    # 1. Gateway is fine but external is bad -> ISP issue
    gw = results.get("gateway_ping")
    pings = results.get("ping", []) or []
    if gw and gw.get("ok"):
        gw_loss = gw.get("loss", 0)
        ext = [p for p in pings if p.get("host") != gw.get("host")]
        ext_loss_avg = sum(p.get("loss") or 0 for p in ext) / len(ext) if ext else 0
        if gw_loss < 5 and ext_loss_avg > 15:
            suggestions.append({
                "level": "warn",
                "title": "Шлюз отвечает, внешние хосты — теряют",
                "body": f"До шлюза loss {gw_loss:.0f}%, до внешних в среднем {ext_loss_avg:.0f}%. Это типично для проблем у провайдера. Покажите MTR провайдеру.",
            })

    if gw and gw.get("avg") and gw["avg"] > 50:
        suggestions.append({
            "level": "warn",
            "title": "Высокая задержка до шлюза",
            "body": f"Avg {gw['avg']:.0f}ms до домашнего шлюза — обычно <5ms по проводу. Проверьте Wi-Fi: канал, перегрузку, расстояние до точки.",
        })

    # 2. High loss to a specific host
    high_loss = [p for p in pings if (p.get("loss") or 0) >= 20 and p.get("host") != (gw or {}).get("host")]
    if high_loss and len(high_loss) < len(pings):
        names = ", ".join(p.get("name") or p.get("host") for p in high_loss[:3])
        suggestions.append({
            "level": "warn",
            "title": "Высокие потери на отдельных хостах",
            "body": f"Loss ≥20% на: {names}. Скорее всего проблема на маршруте к этим хостам, не общая. MTR покажет, где конкретно теряются пакеты.",
        })

    # 3. All external hosts dead -> no internet
    if pings and all((p.get("loss") or 100) >= 95 for p in pings if p.get("host") != (gw or {}).get("host")):
        if gw and gw.get("ok"):
            suggestions.append({
                "level": "error",
                "title": "Нет интернета",
                "body": "Шлюз отвечает, но внешние хосты — нет. Проблема между роутером и провайдером: WAN-порт, кабель, авторизация PPPoE.",
            })
        else:
            suggestions.append({
                "level": "error",
                "title": "Нет сети",
                "body": "Не отвечает даже шлюз. Проверьте кабель/Wi-Fi, перезагрузите роутер.",
            })

    # 4. DNS matrix: system DNS gives different IPs than public
    dns_matrix = results.get("dns_matrix")
    if dns_matrix:
        diffs = 0
        for domain, by_server in (dns_matrix.get("results") or {}).items():
            sys_ip = by_server.get("Системный") or by_server.get("System")
            public_ips = [v for k, v in by_server.items()
                          if k not in ("Системный", "System") and v not in ("FAIL", "—", None)]
            if sys_ip and sys_ip != "FAIL" and public_ips:
                if sys_ip not in public_ips and not any(_same_subnet(sys_ip, p) for p in public_ips):
                    diffs += 1
        if diffs >= 2:
            suggestions.append({
                "level": "warn",
                "title": "Системный DNS даёт другие IP",
                "body": f"По {diffs} доменам системный DNS возвращает адреса, отсутствующие у публичных DNS. Возможно DNS-перехват провайдером, MITM, или устаревший кэш. Попробуйте поменять DNS на 1.1.1.1 / 8.8.8.8.",
            })

    # 5. Public DNS faster than system
    dns_pings = results.get("dns_server_pings")
    if dns_pings and gw and gw.get("avg"):
        fastest_public = min((p["avg"] for p in dns_pings if p.get("avg") is not None), default=None)
        if fastest_public and fastest_public < gw["avg"] + 10:
            # public DNS is reachable, but compare to system DNS responses... harder; suggest by default if RTT < 30ms
            if fastest_public < 30:
                suggestions.append({
                    "level": "info",
                    "title": "Публичные DNS быстры — можно переключиться",
                    "body": f"Быстрейший публичный DNS — {fastest_public:.0f}ms. Переключение на 1.1.1.1 или 8.8.8.8 ускорит резолв на 50-200ms на запрос.",
                })

    # 6. HTTP works but ping fails — site blocks ICMP
    http = results.get("http", []) or []
    for h in http:
        host = _host_from_url(h.get("url", ""))
        ping_for = next((p for p in pings if p.get("host") == host), None)
        if h.get("ok") and ping_for and (ping_for.get("loss") or 0) >= 90:
            suggestions.append({
                "level": "info",
                "title": f"{host} отвечает по HTTP, но ICMP блокирован",
                "body": "Хост недоступен по ping, но HTTP-ответ есть. Это нормально — многие сайты блокируют ICMP. Не показатель проблем.",
            })
            break

    # 7. Trace timeout in middle -> single bad hop
    trace = results.get("trace") or []
    if trace and len(trace) >= 3:
        timeouts = [h for h in trace if h.get("timeout")]
        if 0 < len(timeouts) < len(trace):
            # is there a hop with high loss but successors OK?
            for i, hop in enumerate(trace[:-1]):
                if hop.get("timeout") and not trace[i+1].get("timeout"):
                    suggestions.append({
                        "level": "info",
                        "title": f"Хоп {hop['hop']} молчит, но следующий — отвечает",
                        "body": "Промежуточный маршрутизатор не отвечает на ICMP, но трафик через него идёт. Это нормально, не проблема.",
                    })
                    break

    # 8. MTR: identify lossy hop
    mtr = results.get("mtr") or []
    if mtr:
        lossy_hops = [h for h in mtr if (h.get("loss") or 0) >= 10 and not h.get("timeout")]
        if lossy_hops:
            worst = max(lossy_hops, key=lambda x: x.get("loss") or 0)
            suggestions.append({
                "level": "warn",
                "title": f"Узкое место на хопе {worst.get('hop')}",
                "body": f"IP {worst.get('ip')} теряет {worst.get('loss'):.0f}% пакетов. Это место — основная причина проблем с этим хостом.",
            })

    # 9. Batch: many fails in one category
    batch = results.get("batch")
    if batch and batch.get("results"):
        by_cat: dict = {}
        for r in batch["results"]:
            cat = r.get("category", "other")
            by_cat.setdefault(cat, {"total": 0, "bad": 0})
            by_cat[cat]["total"] += 1
            if r.get("status") in ("FAIL", "WARN"):
                by_cat[cat]["bad"] += 1
        for cat, counts in by_cat.items():
            if counts["total"] >= 3 and counts["bad"] / counts["total"] >= 0.7:
                suggestions.append({
                    "level": "warn",
                    "title": f"Категория «{cat.replace('_', ' ')}» массово недоступна",
                    "body": f"{counts['bad']}/{counts['total']} сайтов категории не отвечают. Возможна блокировка категории провайдером или CDN-проблема.",
                })

    if not suggestions:
        suggestions.append({
            "level": "info",
            "title": "Проблем не обнаружено",
            "body": "Метрики в норме. Подключение стабильное.",
        })

    return suggestions


def _same_subnet(ip1: str, ip2: str, prefix: int = 16) -> bool:
    try:
        a = ip1.split(".")[:prefix // 8]
        b = ip2.split(".")[:prefix // 8]
        return a == b
    except Exception:
        return False


def _host_from_url(url: str) -> str:
    if "://" in url:
        url = url.split("://", 1)[1]
    return url.split("/", 1)[0].split(":", 1)[0]
