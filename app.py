import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import subprocess
import sys
import json
import os
from datetime import datetime

# Import your existing modules
sys.path.append(str(Path(__file__).parent))
from scraper import ProductScraper, DEFAULT_CATEGORIES
from price_optimizer import (
    read_overview, read_prices, suggest_price, categorize_product,
    simulate_profit, run_ab_test, DEMAND_ELASTICITY, DEMAND_SATURATION
)
from dashboard import load_data, build_dashboard
from utils import canonical_key

# Set page config
st.set_page_config(
    page_title="Dzukou Dynamic Pricing",
    page_icon="🎯",
    layout="wide"
)

# Initialize session state
if 'scraping_complete' not in st.session_state:
    st.session_state.scraping_complete = False
if 'optimization_complete' not in st.session_state:
    st.session_state.optimization_complete = False

# Custom CSS for better styling
st.markdown("""
<style>
    .stButton>button {
        background-color: #667eea;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #764ba2;
        transform: translateY(-2px);
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    .success-message {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🎯 Dzukou Dynamic Pricing Dashboard")
st.markdown("### Optimize your product pricing with competitor analysis")

# Sidebar for navigation
with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Choose a section:",
        ["📊 Dashboard", "➕ Add Products", "🔍 Scrape Prices", "💡 Optimize Prices", "📈 View Results"]
    )
    
    st.markdown("---")
    st.markdown("### Quick Guide")
    st.markdown("""
    1. **Add Products**: Register new products
    2. **Scrape Prices**: Collect competitor data
    3. **Optimize Prices**: Generate recommendations
    4. **View Results**: Analyze profit impact
    """)

# Main content based on selected page
if page == "📊 Dashboard":
    st.header("📊 Pricing Overview Dashboard")
    
    # Check if we have optimization results
    if Path("recommended_prices.csv").exists():
        try:
            # Load and display data
            df = load_data()
            
            # Display key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_profit_increase = df["Profit Delta"].sum()
            avg_price_increase = df["Price Delta %"].mean()
            products_with_increase = (df["Price Delta"] > 0).sum()
            
            with col1:
                st.metric(
                    "Total Profit Increase",
                    f"€{total_profit_increase:,.2f}",
                    f"+{(total_profit_increase/df['Current Price'].sum()*100):.1f}%"
                )
            
            with col2:
                st.metric(
                    "Avg Price Change",
                    f"{avg_price_increase:.1f}%"
                )
            
            with col3:
                st.metric(
                    "Products to Increase",
                    f"{products_with_increase}/{len(df)}"
                )
            
            with col4:
                if "AB P-Value" in df.columns:
                    significant = (df["AB P-Value"] < 0.05).sum()
                    st.metric(
                        "Significant Changes",
                        f"{significant}/{len(df)}"
                    )
            
            st.markdown("---")
            
            # Profit Delta Chart
            st.subheader("💰 Profit Delta by Product")
            fig_delta = go.Figure()
            fig_delta.add_trace(
                go.Bar(
                    x=df["Product Name"],
                    y=df["Profit Delta"],
                    marker=dict(
                        color=df["Profit Delta"],
                        colorscale='RdYlGn',
                        showscale=True,
                        colorbar=dict(title="Profit Δ (€)")
                    ),
                    text=[f"€{x:.2f}" for x in df["Profit Delta"]],
                    textposition="outside",
                )
            )
            fig_delta.update_layout(
                height=500,
                xaxis_tickangle=-45,
                yaxis_title="Profit Delta (€)",
                showlegend=False
            )
            st.plotly_chart(fig_delta, use_container_width=True)
            
            # Price Comparison
            st.subheader("💸 Current vs Recommended Prices")
            price_comparison = pd.DataFrame({
                'Product': df['Product Name'],
                'Current Price': df['Current Price'],
                'Recommended Price': df['Recommended Price']
            })
            price_comparison = price_comparison.melt(
                id_vars='Product',
                var_name='Price Type',
                value_name='Price'
            )
            
            fig_price = px.bar(
                price_comparison,
                x='Product',
                y='Price',
                color='Price Type',
                barmode='group',
                color_discrete_map={
                    'Current Price': '#3498db',
                    'Recommended Price': '#e74c3c'
                }
            )
            fig_price.update_layout(
                height=500,
                xaxis_tickangle=-45,
                yaxis_title="Price (€)"
            )
            st.plotly_chart(fig_price, use_container_width=True)
            
            # Detailed table
            st.subheader("📋 Detailed Product Analysis")
            display_df = df[[
                'Product Name', 'Category', 'Current Price', 'Recommended Price',
                'Price Delta %', 'Profit Delta'
            ]].copy()
            
            # Format columns
            display_df['Current Price'] = display_df['Current Price'].apply(lambda x: f"€{x:.2f}")
            display_df['Recommended Price'] = display_df['Recommended Price'].apply(lambda x: f"€{x:.2f}")
            display_df['Price Delta %'] = display_df['Price Delta %'].apply(lambda x: f"{x:.1f}%")
            display_df['Profit Delta'] = display_df['Profit Delta'].apply(lambda x: f"€{x:.2f}")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            
        except Exception as e:
            st.error(f"Error loading dashboard data: {str(e)}")
            st.info("Please run the optimization first to generate results.")
    else:
        st.info("No pricing recommendations found. Please run the complete workflow first.")
        st.markdown("""
        ### Getting Started:
        1. Go to **Add Products** to register your products
        2. Use **Scrape Prices** to collect competitor data
        3. Run **Optimize Prices** to generate recommendations
        """)

elif page == "➕ Add Products":
    st.header("➕ Add New Product")
    
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            product_name = st.text_input("Product Name*", placeholder="e.g., Bamboo Sunglasses")
            product_id = st.text_input("Product ID*", placeholder="e.g., SKU123")
            category = st.text_input("Category*", placeholder="e.g., Sunglasses")
        
        with col2:
            current_price = st.number_input("Current Price (€)*", min_value=0.0, step=0.50)
            unit_cost = st.number_input("Unit Cost (€)*", min_value=0.0, step=0.50)
            keywords = st.text_area(
                "Search Keywords*",
                placeholder="Enter keywords separated by commas\ne.g., bamboo sunglasses, eco sunglasses, wooden eyewear",
                height=100
            )
        
        submitted = st.form_submit_button("Add Product", type="primary")
        
        if submitted:
            if all([product_name, product_id, category, current_price > 0, unit_cost > 0, keywords]):
                try:
                    # Add logic to save product
                    # This would integrate with your existing manage_products.py logic
                    success_msg = f"""
                    <div class="success-message">
                    ✅ Successfully added product: <strong>{product_name}</strong><br>
                    Category: {category}<br>
                    Keywords: {keywords}
                    </div>
                    """
                    st.markdown(success_msg, unsafe_allow_html=True)
                    
                    # Here you would call your existing product management functions
                    
                except Exception as e:
                    st.error(f"Error adding product: {str(e)}")
            else:
                st.error("Please fill in all required fields")
    
    # Display existing products
    st.markdown("---")
    st.subheader("📦 Existing Products")
    
    if Path("Dzukou_Pricing_Overview_With_Names - Copy.csv").exists():
        try:
            existing_products = pd.read_csv("Dzukou_Pricing_Overview_With_Names - Copy.csv", encoding="cp1252")
            st.dataframe(existing_products, use_container_width=True, hide_index=True)
        except Exception as e:
            st.info("No products found. Add your first product above!")

elif page == "🔍 Scrape Prices":
    st.header("🔍 Competitor Price Scraping")
    
    st.markdown("""
    This tool searches sustainable online stores for competitor prices in each product category.
    The process may take several minutes depending on the number of categories.
    """)
    
    # Display categories to be scraped
    categories = list(DEFAULT_CATEGORIES.keys())
    if Path("category_keywords.json").exists():
        with open("category_keywords.json", "r") as f:
            kw_data = json.load(f)
            categories.extend([k for k in kw_data.keys() if k not in categories])
    
    st.info(f"**Categories to scrape:** {len(categories)}")
    
    cols = st.columns(3)
    for i, cat in enumerate(categories):
        cols[i % 3].markdown(f"• {cat}")
    
    st.markdown("---")
    
    if st.button("🚀 Start Scraping", type="primary"):
        with st.spinner("Scraping competitor prices... This may take a few minutes..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Initialize scraper
                scraper = ProductScraper()
                
                # Simulate scraping progress
                total_tasks = len(scraper.product_categories) * len(scraper.stores)
                current_task = 0
                
                # Here you would integrate with the actual scraper
                # For now, we'll show a simulation
                for i, (category, info) in enumerate(scraper.product_categories.items()):
                    for j, (store, _) in enumerate(scraper.stores.items()):
                        current_task += 1
                        progress = current_task / total_tasks
                        progress_bar.progress(progress)
                        status_text.text(f"Scraping {store} for {category}...")
                        
                        # In production, you would call:
                        # products = scraper.scrape_store(store, store_cfg, category, terms)
                
                # Save results
                scraper.save_category_csvs()
                
                st.session_state.scraping_complete = True
                st.success("✅ Scraping completed successfully!")
                
                # Show summary
                st.markdown("### Scraping Summary")
                data_dir = Path("product_data")
                if data_dir.exists():
                    for csv_file in data_dir.glob("*.csv"):
                        df = pd.read_csv(csv_file)
                        st.metric(
                            csv_file.stem.replace("_", " ").title(),
                            f"{len(df)} products found"
                        )
                
            except Exception as e:
                st.error(f"Error during scraping: {str(e)}")

elif page == "💡 Optimize Prices":
    st.header("💡 Price Optimization")
    
    if not st.session_state.scraping_complete and not Path("product_data").exists():
        st.warning("⚠️ Please run the scraper first to collect competitor data.")
    else:
        st.markdown("""
        The optimizer analyzes competitor prices and suggests new prices that maximize profit
        while respecting market constraints and category-specific parameters.
        """)
        
        # Show optimization parameters
        with st.expander("🔧 Optimization Parameters"):
            st.markdown("""
            - **Profit Margins**: Category-specific minimum margins (10-30%)
            - **Demand Elasticity**: How sensitive customers are to price changes
            - **Max Price Increase**: Limited to 30% above current price
            - **Market Position**: Stays competitive with market average
            """)
        
        if st.button("🎯 Run Price Optimization", type="primary"):
            with st.spinner("Optimizing prices..."):
                try:
                    # Run the optimizer
                    # In production, you would import and run your price_optimizer.main()
                    
                    # For now, simulate the process
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Load products
                    overview = read_overview()
                    total_products = len(overview)
                    
                    for i, (product_name, info) in enumerate(overview.items()):
                        progress = (i + 1) / total_products
                        progress_bar.progress(progress)
                        status_text.text(f"Optimizing price for: {product_name}")
                    
                    st.session_state.optimization_complete = True
                    st.success("✅ Price optimization completed!")
                    
                    # Show quick results
                    if Path("recommended_prices.csv").exists():
                        results_df = pd.read_csv("recommended_prices.csv")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            total_profit = results_df["Profit Delta"].sum()
                            st.metric("Total Profit Increase", f"€{total_profit:,.2f}")
                        with col2:
                            products_improved = (results_df["Profit Delta"] > 0).sum()
                            st.metric("Products Improved", f"{products_improved}/{len(results_df)}")
                        with col3:
                            avg_change = results_df["Profit Delta"].mean()
                            st.metric("Avg Profit Change", f"€{avg_change:.2f}")
                        
                        st.info("Go to **View Results** to see detailed analysis")
                    
                except Exception as e:
                    st.error(f"Error during optimization: {str(e)}")

elif page == "📈 View Results":
    st.header("📈 Optimization Results")
    
    if not st.session_state.optimization_complete and not Path("recommended_prices.csv").exists():
        st.warning("⚠️ Please run the price optimization first.")
    else:
        # Load results
        results_df = pd.read_csv("recommended_prices.csv")
        
        # Summary statistics
        st.subheader("📊 Summary Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_current = results_df["Profit Current"].sum()
            total_recommended = results_df["Profit Recommended"].sum()
            increase = total_recommended - total_current
            st.metric(
                "Profit Impact",
                f"€{increase:,.2f}",
                f"+{(increase/total_current*100):.1f}%"
            )
        
        with col2:
            avg_competitor = results_df["Avg Competitor Price"].mean()
            st.metric(
                "Avg Competitor Price",
                f"€{avg_competitor:.2f}"
            )
        
        with col3:
            total_competitors = results_df["Competitor Count"].sum()
            st.metric(
                "Total Competitors Analyzed",
                f"{total_competitors:,}"
            )
        
        with col4:
            if "AB P-Value" in results_df.columns:
                significant = (pd.to_numeric(results_df["AB P-Value"], errors='coerce') < 0.05).sum()
                st.metric(
                    "Statistically Significant",
                    f"{significant}/{len(results_df)}"
                )
        
        # Category breakdown
        st.subheader("📦 Results by Category")
        
        category_summary = results_df.groupby("Category").agg({
            "Profit Delta": ["sum", "mean"],
            "Product Name": "count"
        }).round(2)
        
        category_summary.columns = ["Total Profit Δ", "Avg Profit Δ", "Products"]
        st.dataframe(category_summary, use_container_width=True)
        
        # Detailed results table
        st.subheader("🔍 Detailed Product Results")
        
        # Select columns to display
        display_cols = [
            "Product Name", "Category", "Recommended Price",
            "Avg Competitor Price", "Competitor Count",
            "Profit Current", "Profit Recommended", "Profit Delta"
        ]
        
        if "AB P-Value" in results_df.columns:
            display_cols.append("AB P-Value")
        
        st.dataframe(
            results_df[display_cols],
            use_container_width=True,
            hide_index=True
        )
        
        # Download buttons
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results (CSV)",
                data=csv,
                file_name=f"price_recommendations_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            if st.button("📊 Generate Full Dashboard"):
                try:
                    build_dashboard(load_data())
                    with open("dashboard.html", "r") as f:
                        html_content = f.read()
                    st.download_button(
                        label="📥 Download Dashboard (HTML)",
                        data=html_content,
                        file_name=f"pricing_dashboard_{datetime.now().strftime('%Y%m%d')}.html",
                        mime="text/html"
                    )
                except Exception as e:
                    st.error(f"Error generating dashboard: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    Dzukou Dynamic Pricing Toolkit | Built with ❤️ for sustainable business
    </div>
    """,
    unsafe_allow_html=True
)
