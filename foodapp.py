# app.py
# -----------------------------
# Local Food Wastage Management - Streamlit App
# -----------------------------

import os
import datetime as dt
import pandas as pd
import psycopg2
import streamlit as st
import plotly.express as px

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Food Wastage Management", page_icon="🍽️", layout="wide")

# Sidebar DB credentials (edit defaults for local dev; in prod use st.secrets)
st.sidebar.header("🔐 Database Connection")
DB_HOST = st.sidebar.text_input("Host", os.getenv("PGHOST", "localhost"))
DB_NAME = st.sidebar.text_input("Database", os.getenv("PGDATABASE", "foodapp"))
DB_USER = st.sidebar.text_input("User", os.getenv("PGUSER", "postgres"))
DB_PASS = st.sidebar.text_input("Password", os.getenv("PGPASSWORD", "nagda@321"), type="password")
DB_PORT = int(st.sidebar.text_input("Port", os.getenv("PGPORT", "5432")))

# -----------------------------
# DB helpers
# -----------------------------
def get_conn():
    return psycopg2.connect(
        host="localhost", dbname="foodapp", user="postgres", password="nagda@321", port="5432"
    )

@st.cache_data(ttl=60)
def read_sql(query, params=None):
    conn = get_conn()
    try:
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()

def execute_sql(query, params=None, many=None):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if many is not None:
                    cur.executemany(query, many)
                else:
                    cur.execute(query, params)
    finally:
        conn.close()

# Small utility: robust DATE casting for text date columns
def date_expr(colname):
    # Many CSV imports came as TEXT; use ::date safely
    return f'"{colname}"::date'

# -----------------------------
# Header
# -----------------------------
st.title("🍽️ Local Food Wastage Management System")
st.markdown(
    """
**Goal:** connect surplus food **providers** with **receivers**, reduce waste, and analyze trends.  
Use the tabs below to explore **KPIs**, **EDA**, **15 query insights**, and **CRUD**.
"""
)

# -----------------------------
# Preload DataFrames (cached)
# -----------------------------
providers = read_sql('SELECT * FROM providers;')
receivers = read_sql('SELECT * FROM receivers;')
food = read_sql('SELECT * FROM food_listings;')
claims = read_sql('SELECT * FROM claims;')

# -----------------------------
# Tabs
# -----------------------------
tab_dash, tab_eda, tab_queries, tab_crud, tab_about = st.tabs(
    ["📊 Dashboard", "🔍 EDA", "🧠 15 SQL Insights", "✍️ CRUD", "ℹ️ About"]
)

# =============================
# Dashboard
# =============================
with tab_dash:
    st.subheader("Key Performance Indicators")

    total_food_qty = int(food["Quantity"].fillna(0).sum()) if "Quantity" in food.columns else 0
    total_claims = len(claims)
    completed_claims = int((claims["Status"] == "Completed").sum()) if "Status" in claims.columns else 0
    success_rate = round(100 * completed_claims / total_claims, 2) if total_claims else 0.0
    total_providers = providers["Provider_ID"].nunique() if "Provider_ID" in providers.columns else 0
    total_receivers = receivers["Receiver_ID"].nunique() if "Receiver_ID" in receivers.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🍱 Total Food Quantity", total_food_qty)
    c2.metric("📦 Total Claims", total_claims)
    c3.metric("✅ Success Rate (%)", success_rate)
    c4.metric("🏪 Providers", total_providers)
    c5.metric("👥 Receivers", total_receivers)

    st.markdown("---")
    st.subheader("Visuals")

    colA, colB = st.columns(2)
    with colA:
        if "Status" in claims.columns and not claims.empty:
            fig = px.pie(claims, names="Status", title="Claims by Status")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No claims data available for status pie chart.")

    with colB:
        if {"Provider_ID", "Quantity"}.issubset(food.columns) and "Name" in providers.columns:
            food_by_provider = (
                food.merge(providers[["Provider_ID", "Name"]], on="Provider_ID", how="left")
                .groupby("Name", as_index=False)["Quantity"].sum()
                .sort_values("Quantity", ascending=False)
                .head(10)
            )
            if not food_by_provider.empty:
                fig2 = px.bar(food_by_provider, x="Name", y="Quantity", title="Top Providers by Donated Quantity")
                fig2.update_layout(xaxis_title="Provider", yaxis_title="Total Quantity")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No data to show Top Providers.")
        else:
            st.info("Missing columns to build Top Providers chart.")

# =============================
# EDA
# =============================
with tab_eda:
    st.subheader("Exploratory Data Analysis")

    st.markdown("#### Data Snapshots")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Providers (head)")
        st.dataframe(providers.head(10), use_container_width=True, height=240)
        st.caption("Receivers (head)")
        st.dataframe(receivers.head(10), use_container_width=True, height=240)
    with c2:
        st.caption("Food Listings (head)")
        st.dataframe(food.head(10), use_container_width=True, height=240)
        st.caption("Claims (head)")
        st.dataframe(claims.head(10), use_container_width=True, height=240)

    st.markdown("#### Missing Values Overview")
    def nulls(df, name):
        if df.empty:
            return pd.DataFrame({"column": [], "nulls": [], "pct": []})
        s = df.isna().sum().sort_values(ascending=False)
        res = pd.DataFrame({"column": s.index, "nulls": s.values})
        res["pct"] = (res["nulls"] / len(df) * 100).round(2)
        res.insert(0, "table", name)
        return res
    nv = pd.concat([
        nulls(providers, "providers"),
        nulls(receivers, "receivers"),
        nulls(food, "food_listings"),
        nulls(claims, "claims")
    ], ignore_index=True)
    st.dataframe(nv, use_container_width=True, height=240)

    st.markdown("#### Distributions & Counts")
    col1, col2, col3 = st.columns(3)
    with col1:
        if "Food_Type" in food.columns and not food.empty:
            st.caption("Food Type Distribution")
            ft = food["Food_Type"].value_counts().reset_index()
            ft.columns = ["Food_Type", "count"]
            st.bar_chart(ft.set_index("Food_Type"))
        else:
            st.info("No Food_Type column/data.")

    with col2:
        if "Meal_Type" in food.columns and not food.empty:
            st.caption("Meal Type Distribution")
            mt = food["Meal_Type"].value_counts().reset_index()
            mt.columns = ["Meal_Type", "count"]
            st.bar_chart(mt.set_index("Meal_Type"))
        else:
            st.info("No Meal_Type column/data.")

    with col3:
        if "Status" in claims.columns and not claims.empty:
            st.caption("Claims by Status")
            cs = claims["Status"].value_counts().reset_index()
            cs.columns = ["Status", "count"]
            st.bar_chart(cs.set_index("Status"))
        else:
            st.info("No Status column/data.")

    st.markdown("#### Quantity Histogram")
    if "Quantity" in food.columns and not food.empty:
        q = food["Quantity"].dropna()
        fig = px.histogram(q, nbins=20, title="Quantity Distribution")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No quantity data for histogram.")

# =============================
# 15 SQL Insights
# =============================
with tab_queries:
    st.subheader("🧠 Insights (15 SQL Queries)")

    # Filters for some queries
    st.sidebar.markdown("---")
    st.sidebar.header("🔎 Filters")
    city_filter = st.sidebar.text_input("Filter by City (exact match)", "")
    provider_city = city_filter.strip() if city_filter else None

    # Helper to render query with dataframe and optional chart
    def render_query(title, sql, params=None, chart_kind=None, x=None, y=None):
        st.markdown(f"**{title}**")
        df = read_sql(sql, params=params)
        st.dataframe(df, use_container_width=True)
        if chart_kind == "bar" and df.shape[0] and x and y and x in df.columns and y in df.columns:
            fig = px.bar(df, x=x, y=y)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")

    # 1
    render_query(
        "1) How many food providers and receivers are there in each city?",
        """
        SELECT "City",
               COUNT(DISTINCT "Provider_ID") AS total_providers,
               COUNT(DISTINCT "Receiver_ID") AS total_receivers
        FROM (
            SELECT "City", "Provider_ID", NULL::int AS "Receiver_ID" FROM providers
            UNION ALL
            SELECT "City", NULL::int, "Receiver_ID" FROM receivers
        ) t
        GROUP BY "City"
        ORDER BY "City";
        """,
        chart_kind="bar", x="City", y="total_providers"
    )

    # 2
    render_query(
        "2) Which type of food provider contributes the most food (by total quantity)?",
        """
        SELECT "Provider_Type", SUM("Quantity") AS total_quantity
        FROM food_listings
        GROUP BY "Provider_Type"
        ORDER BY total_quantity DESC
        LIMIT 1;
        """
    )

    # 3
    render_query(
        "3) Contact info of providers in a specific city",
        """
        SELECT "Name", "Type", "Contact", "Address"
        FROM providers
        WHERE (%s IS NULL) OR ("City" = %s);
        """,
        params=[provider_city, provider_city]
    )

    # 4
    render_query(
        "4) Which receivers have claimed the most food?",
        """
        SELECT r."Name", r."City", COUNT(c."Claim_ID") AS total_claims
        FROM claims c
        JOIN receivers r ON c."Receiver_ID" = r."Receiver_ID"
        GROUP BY r."Name", r."City"
        ORDER BY total_claims DESC
        LIMIT 5;
        """
    )

    # 5
    render_query(
        "5) Total quantity of food available from all providers",
        """SELECT SUM("Quantity") AS total_food_available FROM food_listings;"""
    )

    # 6
    render_query(
        "6) Which city has the highest number of food listings?",
        """
        SELECT p."City", COUNT(f."Food_ID") AS total_listings
        FROM food_listings f
        JOIN providers p ON f."Provider_ID" = p."Provider_ID"
        GROUP BY p."City"
        ORDER BY total_listings DESC
        LIMIT 1;
        """
    )

    # 7
    render_query(
        "7) Most commonly available food types",
        """
        SELECT "Food_Type", COUNT("Food_ID") AS total_items
        FROM food_listings
        GROUP BY "Food_Type"
        ORDER BY total_items DESC;
        """,
        chart_kind="bar", x="Food_Type", y="total_items"
    )

    # 8
    render_query(
        "8) How many food claims have been made for each food item?",
        """
        SELECT f."Food_Name", COUNT(c."Claim_ID") AS total_claims
        FROM claims c
        JOIN food_listings f ON c."Food_ID" = f."Food_ID"
        GROUP BY f."Food_Name"
        ORDER BY total_claims DESC;
        """,
        chart_kind="bar", x="Food_Name", y="total_claims"
    )

    # 9
    render_query(
        "9) Which provider has the highest number of successful claims?",
        """
        SELECT p."Name", COUNT(c."Claim_ID") AS successful_claims
        FROM claims c
        JOIN food_listings f ON c."Food_ID" = f."Food_ID"
        JOIN providers p ON f."Provider_ID" = p."Provider_ID"
        WHERE c."Status" = 'Completed'
        GROUP BY p."Name"
        ORDER BY successful_claims DESC
        LIMIT 1;
        """
    )

    # 10
    render_query(
        "10) Percentage of claims by status",
        """
        SELECT "Status",
               COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() AS percentage
        FROM claims
        GROUP BY "Status";
        """,
        chart_kind="bar", x="Status", y="percentage"
    )

    # 11
    render_query(
        "11) Average quantity of food claimed per receiver",
        """
        SELECT r."Name", ROUND(AVG(f."Quantity"),2) AS avg_quantity_claimed
        FROM claims c
        JOIN food_listings f ON c."Food_ID" = f."Food_ID"
        JOIN receivers r ON c."Receiver_ID" = r."Receiver_ID"
        GROUP BY r."Name"
        ORDER BY avg_quantity_claimed DESC;
        """
    )

    # 12
    render_query(
        "12) Which meal type is claimed the most?",
        """
        SELECT f."Meal_Type", COUNT(c."Claim_ID") AS total_claims
        FROM claims c
        JOIN food_listings f ON c."Food_ID" = f."Food_ID"
        GROUP BY f."Meal_Type"
        ORDER BY total_claims DESC;
        """,
        chart_kind="bar", x="Meal_Type", y="total_claims"
    )

    # 13
    render_query(
        "13) Total quantity of food donated by each provider",
        """
        SELECT p."Name", SUM(f."Quantity") AS total_donated
        FROM food_listings f
        JOIN providers p ON f."Provider_ID" = p."Provider_ID"
        GROUP BY p."Name"
        ORDER BY total_donated DESC;
        """,
        chart_kind="bar", x="Name", y="total_donated"
    )

    # 14
    render_query(
        "14) Which city has the highest number of successful claims?",
        """
        SELECT r."City", COUNT(c."Claim_ID") AS successful_claims
        FROM claims c
        JOIN receivers r ON c."Receiver_ID" = r."Receiver_ID"
        WHERE c."Status" = 'Completed'
        GROUP BY r."City"
        ORDER BY successful_claims DESC
        LIMIT 1;
        """
    )

    # 15 (cast Expiry_Date TEXT -> DATE for comparison)
    render_query(
        "15) Which food item is closest to expiry but still available?",
        f"""
        SELECT "Food_Name", "Expiry_Date", "Quantity"
        FROM food_listings
        WHERE {date_expr("Expiry_Date")} > CURRENT_DATE
        ORDER BY {date_expr("Expiry_Date")} ASC
        LIMIT 1;
        """
    )

# =============================
# =============================
# CRUD Operations
# =============================
with tab_crud:
    st.subheader("✍️ CRUD Operations")

    crud_tabs = st.tabs([
        "➕ Add Food Listing", 
        "📋 View Food Listings", 
        "♻️ Update Quantity", 
        "🗑 Delete Food Listing", 
        "📥 Create Claim", 
        "📋 View Claims", 
        "✅ Update Claim Status", 
        "🗑 Delete Claim"
    ])

    # -----------------------------
    # 1. Add Food Listing
    # -----------------------------
    with crud_tabs[0]:
        st.markdown("Add a new food listing")
        with st.form("add_food_form"):
            f_name = st.text_input("Food Name")
            f_qty = st.number_input("Quantity", min_value=1, value=1)
            f_exp = st.date_input("Expiry Date")
            f_pid = st.number_input("Provider_ID", min_value=1, value=1)
            f_ptype = st.text_input("Provider_Type", value="Restaurant")
            f_loc = st.text_input("Location", value="Unknown")
            f_ftype = st.text_input("Food_Type", value="Vegetarian")
            f_meal = st.text_input("Meal_Type", value="Lunch")
            submitted = st.form_submit_button("Add Listing")

            if submitted:
                execute_sql(
                    """
                    INSERT INTO food_listings
                    ("Food_Name","Quantity","Expiry_Date","Provider_ID","Provider_Type","Location","Food_Type","Meal_Type")
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
                    """,
                    params=(f_name,f_qty,f_exp,f_pid,f_ptype,f_loc,f_ftype,f_meal)
                )
                st.success("✅ Food listing added successfully.")

    # -----------------------------
    # 2. View Food Listings
    # -----------------------------
    with crud_tabs[1]:
        st.markdown("All food listings")
        food_df = read_sql('SELECT * FROM food_listings ORDER BY "Food_ID" DESC LIMIT 500;')
        st.dataframe(food_df, use_container_width=True)

    # -----------------------------
    # 3. Update Quantity
    # -----------------------------
    with crud_tabs[2]:
        st.markdown("Update quantity of a food listing")
        food_df = read_sql('SELECT "Food_ID","Food_Name","Quantity" FROM food_listings ORDER BY "Food_ID";')
        if not food_df.empty:
            options = food_df.apply(lambda r: f'{r["Food_ID"]} — {r["Food_Name"]} (qty: {r["Quantity"]})', axis=1).tolist()
            idx = st.selectbox("Select a listing", list(range(len(options))), format_func=lambda i: options[i])
            new_qty = st.number_input("New Quantity", min_value=0, value=int(food_df.iloc[idx]["Quantity"]))
            if st.button("Update Quantity"):
                execute_sql(
                    'UPDATE food_listings SET "Quantity"=%s WHERE "Food_ID"=%s;',
                    params=(int(new_qty), int(food_df.iloc[idx]["Food_ID"]))
                )
                st.success("✅ Quantity updated successfully.")

    # -----------------------------
    # 4. Delete Food Listing
    # -----------------------------
    with crud_tabs[3]:
        st.markdown("Delete a food listing")
        food_df = read_sql('SELECT "Food_ID","Food_Name" FROM food_listings ORDER BY "Food_ID";')
        if not food_df.empty:
            options = food_df.apply(lambda r: f'{r["Food_ID"]} — {r["Food_Name"]}', axis=1).tolist()
            idx = st.selectbox("Select listing to delete", list(range(len(options))), format_func=lambda i: options[i])
            if st.button("Delete Listing"):
                execute_sql(
                    'DELETE FROM food_listings WHERE "Food_ID"=%s;',
                    params=(int(food_df.iloc[idx]["Food_ID"]),)
                )
                st.success("🗑 Food listing deleted successfully.")

    # -----------------------------
    # 5. Create Claim
    # -----------------------------
    with crud_tabs[4]:
        st.markdown("Create a new claim")
        foods = read_sql('SELECT "Food_ID","Food_Name" FROM food_listings ORDER BY "Food_ID";')
        recs = read_sql('SELECT "Receiver_ID","Name" FROM receivers ORDER BY "Receiver_ID";')
        if not foods.empty and not recs.empty:
            f_idx = st.selectbox("Food", list(range(len(foods))), format_func=lambda i: f'{foods.iloc[i]["Food_ID"]} — {foods.iloc[i]["Food_Name"]}')
            r_idx = st.selectbox("Receiver", list(range(len(recs))), format_func=lambda i: f'{recs.iloc[i]["Receiver_ID"]} — {recs.iloc[i]["Name"]}')
            status = st.selectbox("Status", ["Pending", "Completed", "Cancelled"])
            if st.button("Create Claim"):
                execute_sql(
                    """
                    INSERT INTO claims ("Food_ID","Receiver_ID","Status")
                    VALUES (%s,%s,%s);
                    """,
                    params=(int(foods.iloc[f_idx]["Food_ID"]), int(recs.iloc[r_idx]["Receiver_ID"]), status)
                )
                st.success("✅ Claim created successfully.")

    # -----------------------------
    # 6. View Claims
    # -----------------------------
    with crud_tabs[5]:
        st.markdown("All claims")
        claims_df = read_sql('SELECT * FROM claims ORDER BY "Claim_ID" DESC LIMIT 500;')
        st.dataframe(claims_df, use_container_width=True)

    # -----------------------------
    # 7. Update Claim Status
    # -----------------------------
    with crud_tabs[6]:
        st.markdown("Update claim status")
        claims_df = read_sql('SELECT "Claim_ID","Food_ID","Receiver_ID","Status" FROM claims ORDER BY "Claim_ID";')
        if not claims_df.empty:
            options = claims_df.apply(lambda r: f'#{r["Claim_ID"]} — Food {r["Food_ID"]} / Receiver {r["Receiver_ID"]} [{r["Status"]}]', axis=1).tolist()
            idx = st.selectbox("Select Claim", list(range(len(options))), format_func=lambda i: options[i])
            new_status = st.selectbox("New Status", ["Pending", "Completed", "Cancelled"])
            if st.button("Update Status"):
                execute_sql(
                    'UPDATE claims SET "Status"=%s WHERE "Claim_ID"=%s;',
                    params=(new_status, int(claims_df.iloc[idx]["Claim_ID"]))
                )
                st.success("✅ Claim status updated successfully.")

    # -----------------------------
    # 8. Delete Claim
    # -----------------------------
    with crud_tabs[7]:
        st.markdown("Delete a claim")
        claims_df = read_sql('SELECT "Claim_ID","Food_ID","Receiver_ID" FROM claims ORDER BY "Claim_ID";')
        if not claims_df.empty:
            options = claims_df.apply(lambda r: f'#{r["Claim_ID"]} — Food {r["Food_ID"]} / Receiver {r["Receiver_ID"]}', axis=1).tolist()
            idx = st.selectbox("Select Claim to Delete", list(range(len(options))), format_func=lambda i: options[i])
            if st.button("Delete Claim"):
                execute_sql(
                    'DELETE FROM claims WHERE "Claim_ID"=%s;',
                    params=(int(claims_df.iloc[idx]["Claim_ID"]),)
                )
                st.success("🗑 Claim deleted successfully.")
    
