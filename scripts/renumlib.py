# -*- coding: utf-8 -*-
"""js/core/model.js 의 renumber() 를 그대로 옮긴 것.

화면이 트리를 읽을 때마다 조 번호를 다시 매기므로, 자료를 손으로 고칠
때에도 같은 잣대로 매겨야 한다. 두 곳이 어긋나면 옮김표가 거짓이 된다.
"""


def renumber(nodes):
    state = {"jo": 0}

    def rec(lst, in_annex):
        counters = {"편": 0, "장": 0, "절": 0, "관": 0}
        anx = {}
        for n in lst:
            branch = in_annex or bool(n.get("isAnnex"))
            if n.get("level") == "규정":
                state["jo"] = 0
                rec(n.get("children") or [], False)
                continue
            if n.get("annexRef"):
                g = n["annexRef"].get("gubun") or "별표"
                anx[g] = anx.get(g, 0) + 1
                n["annexRef"]["no"] = str(anx[g])
            elif branch:
                pass
            elif n.get("level") == "조":
                state["jo"] += 1
                n["no"] = state["jo"]
                n["branch"] = 0
            else:
                lv = n.get("level")
                counters[lv] = counters.get(lv, 0) + 1
                n["no"] = counters[lv]
            rec(n.get("children") or [], branch)
            if n.get("isAnnex"):
                g = next((c["annexRef"].get("gubun") for c in n.get("children") or []
                          if c.get("annexRef")), None) or n.get("annexGubun") or "별표"
                n["annexGubun"] = g
                n["title"] = "%s (%d건)" % (g, len(n.get("children") or []))
    rec(nodes, False)
    return nodes
