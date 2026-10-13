"""SDK Scout Agent - screens. Start it with 'Start SDK Scout Agent.bat'."""
import pandas as pd
import streamlit as st

from scout import config, export, pipeline, scoring, store

st.set_page_config(page_title="SDK Scout Agent", page_icon="🎯", layout="wide")

TYPE_OPTIONS = [
    "IIMs, IITs, NITs and other central institutes",
    "Central and state universities",
    "Private universities",
    "B-schools / management institutes",
    "Engineering and medical colleges",
]
SIGNAL_OPTIONS = [
    "Tenders / RFQs for hostel or outpass management",
    "Biometric or facial-recognition access procurement",
    "Hostel digitization / hostel management software",
    "Smart-campus programmes",
    "Campus security modernization",
    "Student ERP modernization",
    "Manual / register-based student movement",
    "Campus expansion",
]
PRIORITY_COLOR = {"High": "green", "Medium": "orange", "Low": "red", "Thin evidence": "gray"}

has_key = bool(config.api_key())
key_problem = config.key_problem()
if key_problem:
    has_key = False  # fall back to demo mode until the key is fixed

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🎯 SDK Scout Agent")
    st.caption("Finds the campuses most likely to need SDKLife's Outpass module, with evidence.")
    if has_key:
        st.success(f"API key found · {config.provider_name()} ({config.model()})")
        use_demo = st.toggle("Demo mode (sample data, no cost)", value=False)
    else:
        if key_problem:
            st.error(key_problem)
        else:
            st.warning(f"No API key yet. Open **config.env**, paste your {config.provider_name()} key after "
                       f"`{config.key_var()}=`, save, and restart. Until then you can explore with sample data.")
        use_demo = True
        st.toggle("Demo mode (sample data, no cost)", value=True, disabled=True)
    if use_demo:
        st.info("Demo mode: every college shown is invented.")
    st.divider()
    st.caption("The score only orders the list. Open any college to see the evidence behind it.")

tab_search, tab_ranked = st.tabs(["1 · Define search", "2 · Ranked prospects"])

# ------------------------------------------------------------ define search
with tab_search:
    st.subheader("Who should the agent look for?")
    c1, c2 = st.columns(2)
    states = c1.text_input("State / region", value="Rajasthan")
    cities = c2.text_area("Cities (comma separated)", value="Udaipur, Jaipur, Jodhpur, Kota, Ajmer, Pilani", height=70)
    types = st.multiselect("Institution types", TYPE_OPTIONS, default=TYPE_OPTIONS)
    c3, c4, c5 = st.columns(3)
    min_hostel = c3.number_input("Minimum students living in hostels", 0, 20000, 500, step=100)
    max_colleges = c4.slider("Number of colleges to research", 3, 30, 5 if not use_demo else 5,
                             help="Start small. Each college uses several web searches.")
    residential_only = c5.checkbox("Residential campuses only", value=True)
    interests = st.multiselect("Optional: signals you care about most (leave empty for all)", SIGNAL_OPTIONS)

    if not use_demo:
        if config.provider() == "groq":
            st.caption("Groq's free plan allows only a few thousand tokens per minute, so expect about a minute "
                       "or two per college, and a daily cap. Try 3-5 colleges first. Finished colleges are always saved.")
        else:
            st.caption("Each college takes a minute or two. Try 3-5 colleges first. Free keys have daily limits; "
                       "everything finished so far is saved.")

    if st.button("Start discovery", type="primary"):
        params = {"states": states.strip(), "cities": cities.strip(), "types": types, "min_hostel": int(min_hostel),
                  "max_colleges": int(max_colleges), "residential_only": residential_only,
                  "signals_of_interest": interests}
        bar = st.progress(0.0, text="Starting...")

        def on_progress(done, total, msg):
            bar.progress(min(1.0, done / max(total, 1)), text=msg)

        try:
            run = pipeline.run_search(params, use_demo, on_progress)
            st.session_state["run_id"] = run["id"]
            bar.progress(1.0, text="Done")
            st.success(f"Finished. {len(run['institutions'])} colleges researched. Open the "
                       "**Ranked prospects** tab.")
        except Exception as exc:
            bar.empty()
            msg = str(exc)
            st.error(f"The search stopped: {msg}")
            low = msg.lower()
            if any(k in low for k in ("invalid api key", "api key not valid", "api_key_invalid", "authentication",
                                      "401", "invalid x-api-key")):
                st.info(f"The API key in config.env is wrong or not saved. Paste the {config.provider_name()} key "
                        f"after {config.key_var()}=, save, close the black window and start the agent again.")
            elif any(k in low for k in ("429", "rate limit", "rate_limit", "resource_exhausted", "quota", "tokens per")):
                st.info("The AI service's usage limit was reached (common on free plans). Wait a few minutes, or "
                        "until tomorrow if the daily limit is used up, then run again with fewer colleges. "
                        "Finished colleges are saved.")
            elif "web search returned nothing" in low:
                st.info("The free web search is being limited right now. Wait a few minutes and try again, or add a "
                        "free Tavily key as TAVILY_API_KEY in config.env for steadier search.")
            elif any(k in low for k in ("403", "permission", "not enabled", "billing")):
                st.info("The AI service refused the request. Check the key and that your account is active.")
            elif "404" in low or "not found" in low or "decommissioned" in low:
                st.info("The model name was not accepted. Check the model line (GROQ_MODEL / GEMINI_MODEL) in config.env.")

# ---------------------------------------------------------- ranked prospects
with tab_ranked:
    runs = store.list_runs()
    if not runs:
        st.info("No searches yet. Run one in the first tab.")
        st.stop()

    ids = [r["id"] for r in runs]
    default = ids.index(st.session_state["run_id"]) if st.session_state.get("run_id") in ids else 0
    run_id = st.selectbox("Search", ids, index=default,
                          format_func=lambda i: next(f"{r['label']} - {r['count']} colleges" for r in runs if r["id"] == i))
    run = store.load_run(run_id)
    if run.get("demo"):
        st.warning("This is a demo run. The colleges are invented.")

    decisions = store.load_decisions()
    rows = pipeline.ranked(run)

    f1, f2 = st.columns(2)
    pr_filter = f1.multiselect("Priority", list(scoring.PRIORITY_ORDER), default=list(scoring.PRIORITY_ORDER))
    dec_filter = f2.multiselect("Your decision", store.DECISION_OPTIONS, default=store.DECISION_OPTIONS)

    table, visible = [], []
    for r in rows:
        s = r["score"]
        dec = decisions.get(store.inst_key(r), "Not reviewed")
        if s["priority"] not in pr_filter or dec not in dec_filter:
            continue
        visible.append(r)
        top = next((g for g in sorted(s["signals"], key=lambda g: -scoring.TIER_RANK[g["tier"]]) if g["verified"]), None)
        table.append({
            "Priority": s["priority"], "Score": s["adjusted"], "Institution": r["name"], "City": r["city"],
            "Hostel students": r.get("research", {}).get("hostel_students"),
            "Top signal": f"{scoring.TIER_LABEL[top['tier']]}: {top['description']}" if top else "None sourced",
            "Confidence": s["confidence"], "Decision": dec,
        })
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    st.download_button("Download as Excel", export.run_to_excel(run),
                       file_name=f"sdk_scout_{run['id']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if not visible:
        st.stop()

    st.divider()
    names = [f"{r['name']} ({r['city']})" for r in visible]
    pick = st.selectbox("Open a prospect", names)
    r = visible[names.index(pick)]
    s, d = r["score"], r.get("research", {})

    # --- prospect page
    color = PRIORITY_COLOR.get(s["priority"], "gray")
    st.header(r["name"])
    st.markdown(f"**:{color}[{s['priority']}]** · score **{s['adjusted']}** / 100 "
                f"(before confidence adjustment {s['raw']}, evidence confidence {s['confidence']} x{s['multiplier']})")
    st.caption(f"{r['type']} · {r['city']}, {r['state']}" + (f" · {r['website']}" if r.get("website") else ""))
    for flag in s["flags"]:
        st.warning(flag)
    if r.get("error"):
        st.error("Research failed for this college. Run the search again later.")

    a, b = st.columns(2)
    with a:
        st.markdown("**Why shortlisted**")
        st.write(d.get("why_shortlisted") or "-")
        st.markdown("**Campus profile**")
        st.write(d.get("campus_summary") or "-")
        if d.get("hostel_students") is not None:
            st.caption(f"Hostel students: about {d['hostel_students']:,}. {d.get('hostel_students_basis', '')}")
    with b:
        st.markdown("**Potential SDKLife fit**")
        st.write(d.get("potential_fit") or "-")
        st.markdown("**Recommended outreach angle**")
        st.write(d.get("outreach_angle") or "-")

    st.markdown("**How the score was built**")
    st.dataframe(pd.DataFrame(s["breakdown"]).rename(columns={"dimension": "Dimension", "points": "Points",
                                                              "max": "Out of", "note": "Why"}),
                 hide_index=True, width="stretch")

    st.markdown("**Signals and evidence**")
    counted = [g for g in s["signals"] if g["verified"]]
    if counted:
        for g in sorted(counted, key=lambda g: -scoring.TIER_RANK[g["tier"]]):
            link = f"[{g.get('source_title') or g['source_url']}]({g['source_url']})"
            st.markdown(f"- **{scoring.TIER_LABEL[g['tier']]}** ({scoring.TIER_STRENGTH[g['tier']]}) · "
                        f"{g.get('date', 'date unknown')} · {g.get('description', '')} — {link}")
    else:
        st.write("No sourced signals were found.")
    leads = [g for g in s["signals"] if not g["verified"]]
    if leads:
        with st.expander(f"{len(leads)} lead(s) to check by hand (not counted in the score)"):
            for g in leads:
                st.markdown(f"- {scoring.TIER_LABEL[g['tier']]} · {g.get('description', '')} "
                            f"— claimed source: {g.get('source_url') or 'none'}")
    if d.get("gaps"):
        st.caption(f"Could not find: {d['gaps']}")

    key = store.inst_key(r)
    current = decisions.get(key, "Not reviewed")

    def _save(rec=r, widget=f"dec_{run_id}_{key}"):
        store.set_decision(rec, st.session_state[widget])

    st.radio("Your decision", store.DECISION_OPTIONS, index=store.DECISION_OPTIONS.index(current),
             horizontal=True, key=f"dec_{run_id}_{key}", on_change=_save)
