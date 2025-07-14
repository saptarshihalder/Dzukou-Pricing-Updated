import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import zipfile
import tempfile
import shutil
import json
import io
from datetime import datetime

# Import your optimization modules
from price_optimizer import (
    read_overview, read_prices, suggest_price, categorize_product,
    simulate_profit, run_ab_test, DEMAND_ELASTICITY, DEMAND_SATURATION
)
from dashboard import load_data, build_dashboard

# Page config
st.set_page_config(
    page_title="Dzukou Dynamic Pricing Dashboard",
    page_icon="🎯",
    layout="wide"
)

# Initialize session state
if 'data_uploaded' not in st.session_state:
    st.session_state.data_uploaded = False
if 'scraper_data' not in st.session_state:
    st.session_state.scraper_data = {}
if 'optimization_complete' not in st.session_state:
    st.session_state.optimization_complete = False

# Custom CSS
st.markdown("""
<style>
    .upload-box {
        border: 3px dashed #667eea;
        border-radius: 20px;
        padding: 40px;
        text-align: center;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        margin: 20px 0;
    }
    .upload-box h3 {
        color: #667eea;
        margin-bottom: 20px;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 20px;
        margin: 20px 0;
    }
    .instruction-box {
        background: #e8f4f8;
        border-left: 4px solid #667eea;
        padding: 15px;
        margin: 15px 0;
        border-radius: 5px;
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🎯 Dzukou Dynamic Pricing Dashboard")
st.markdown("### Cloud-based pricing optimization system")

# Sidebar navigation
with st.sidebar:
    st.header("Navigation")
    
    # Show upload status
    if st.session_state.data_uploaded:
        st.success("✅ Data uploaded")
    else:
        st.warning("⚠️ Please upload data first")
    
    page = st.radio(
        "Select Page:",
        ["📤 Upload Data", "💡 Optimize Prices", "📊 View Dashboard", "📈 Analysis", "ℹ️ Instructions"]
    )

# Page: Upload Data
if page == "📤 Upload Data":
    st.header("📤 Upload Scraper Data")
    
    # Instructions
    with st.expander("📋 How to prepare your data", expanded=True):
        st.markdown("""
        ### Step 1: Run the scraper locally
        1. Open terminal/command prompt on your computer
        2. Navigate to your project folder
        3. Run: `python scraper.py`
        4. Wait for scraping to complete
        
        ### Step 2: Prepare the upload
        You can upload data in two ways:
        - **Option A**: Upload individual CSV files from `product_data/` folder
        - **Option B**: Create a ZIP file of the entire `product_data/` folder
        
        ### Required files:
        - All CSV files from `product_data/` folder
        - `Dzukou_Pricing_Overview_With_Names - Copy.csv`
        - `product_data_mapping.csv`
        - `category_keywords.json` (optional)
        """)
    
    # File upload section
    st.markdown("<div class='upload-box'>", unsafe_allow_html=True)
    st.markdown("### 📁 Choose your upload method")
    
    upload_method = st.radio(
        "Select method:",
        ["Upload ZIP file (recommended)", "Upload individual CSV files"]
    )
    
    if upload_method == "Upload ZIP file (recommended)":
        st.markdown("#### Upload a ZIP file containing all your data")
        uploaded_zip = st.file_uploader(
            "Choose ZIP file",
            type=['zip'],
            help="Create a ZIP of your product_data folder and other required files"
        )
        
        if uploaded_zip is not None:
            # Process ZIP file
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extract ZIP
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)
                
                # Process extracted files
                st.success("✅ ZIP file uploaded successfully!")
                
                # Look for product_data folder or CSV files
                csv_files = list(temp_path.rglob("*.csv"))
                json_files = list(temp_path.rglob("*.json"))
                
                if csv_files:
                    st.write(f"Found {len(csv_files)} CSV files")
                    
                    # Store data in session state
                    for csv_file in csv_files:
                        df = pd.read_csv(csv_file, encoding='utf-8', errors='ignore')
                        file_name = csv_file.name
                        st.session_state.scraper_data[file_name] = df
                        st.write(f"- {file_name}: {len(df)} rows")
                    
                    st.session_state.data_uploaded = True
                    st.balloons()
                else:
                    st.error("No CSV files found in the ZIP!")
    
    else:
        st.markdown("#### Upload individual files")
        
        # Multiple file uploader
        uploaded_files = st.file_uploader(
            "Choose CSV files",
            type=['csv'],
            accept_multiple_files=True,
            help="Select all CSV files from your product_data folder"
        )
        
        # Overview file
        overview_file = st.file_uploader(
            "Upload Overview CSV",
            type=['csv'],
            help="Dzukou_Pricing_Overview_With_Names - Copy.csv"
        )
        
        # Mapping file
        mapping_file = st.file_uploader(
            "Upload Mapping CSV",
            type=['csv'],
            help="product_data_mapping.csv"
        )
        
        if uploaded_files and overview_file and mapping_file:
            # Process files
            st.success("✅ Files uploaded successfully!")
            
            # Store in session state
            for file in uploaded_files:
                df = pd.read_csv(file, encoding='utf-8', errors='ignore')
                st.session_state.scraper_data[file.name] = df
                
            # Store special files
            st.session_state.scraper_data['overview'] = pd.read_csv(overview_file, encoding='cp1252', errors='ignore')
            st.session_state.scraper_data['mapping'] = pd.read_csv(mapping_file)
            
            st.session_state.data_uploaded = True
            
            # Show summary
            st.write("### 📊 Upload Summary")
            for name, df in st.session_state.scraper_data.items():
                if name not in ['overview', 'mapping']:
                    st.write(f"- {name}: {len(df)} products")
    
    st.markdown("</div>", unsafe_allow_html=True)

# Page: Optimize Prices
elif page == "💡 Optimize Prices":
    st.header("💡 Price Optimization")
    
    if not st.session_state.data_uploaded:
        st.warning("⚠️ Please upload data first!")
        st.stop()
    
    st.markdown("""
    The optimizer will analyze competitor prices and suggest optimal pricing for each product.
    """)
    
    # Show optimization parameters
    with st.expander("⚙️ Optimization Settings"):
        col1, col2 = st.columns(2)
        with col1:
            max_increase = st.slider("Max price increase %", 0, 50, 30)
            max_decrease = st.slider("Max price decrease %", 0, 50, 25)
        with col2:
            st.info("""
            - **Demand elasticity**: How sensitive customers are to price
            - **Profit margins**: Minimum acceptable margins by category
            - **Market position**: Stay competitive with averages
            """)
    
    if st.button("🚀 Run Price Optimization", type="primary"):
        with st.spinner("Optimizing prices..."):
            try:
                # Get data from session state
                overview_df = st.session_state.scraper_data.get('overview')
                mapping_df = st.session_state.scraper_data.get('mapping')
                
                if overview_df is None or mapping_df is None:
                    st.error("Missing required files!")
                    st.stop()
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = []
                total_products = len(mapping_df)
                
                # Process each product
                for idx, row in mapping_df.iterrows():
                    progress = (idx + 1) / total_products
                    progress_bar.progress(progress)
                    
                    product_name = row['Product Name'].strip()
                    data_file = row['Data File'].strip()
                    
                    status_text.text(f"Optimizing: {product_name}")
                    
                    # Get product info from overview
                    product_info = overview_df[overview_df['Product Name'] == product_name]
                    if product_info.empty:
                        continue
                    
                    current_price = float(str(product_info.iloc[0][' Current Price ']).replace('€', '').strip())
                    unit_cost = float(str(product_info.iloc[0][' Unit Cost ']).replace('€', '').strip())
                    
                    # Get competitor prices
                    data_file_name = Path(data_file).name
                    if data_file_name in st.session_state.scraper_data:
                        competitor_df = st.session_state.scraper_data[data_file_name]
                        prices = competitor_df['price'].dropna().tolist()
                        prices = [p for p in prices if p > 0]
                    else:
                        prices = []
                    
                    # Determine category and optimize
                    category = categorize_product(product_name)
                    
                    if prices:
                        # Your existing optimization logic
                        recommended_price = suggest_price(
                            product_name,
                            category,
                            prices,
                            current_price,
                            unit_cost
                        )
                        
                        # Calculate metrics
                        avg_competitor = sum(prices) / len(prices) if prices else current_price
                        
                        results.append({
                            'Product Name': product_name,
                            'Product ID': row['Product ID'],
                            'Category': category,
                            'Current Price': current_price,
                            'Recommended Price': recommended_price,
                            'Avg Competitor Price': avg_competitor,
                            'Competitor Count': len(prices),
                            'Price Change %': ((recommended_price - current_price) / current_price) * 100
                        })
                
                # Store results
                st.session_state.optimization_results = pd.DataFrame(results)
                st.session_state.optimization_complete = True
                
                progress_bar.progress(1.0)
                status_text.text("Optimization complete!")
                
                # Show summary
                st.success(f"✅ Optimized {len(results)} products successfully!")
                
                # Quick metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    avg_change = st.session_state.optimization_results['Price Change %'].mean()
                    st.metric("Average Price Change", f"{avg_change:.1f}%")
                with col2:
                    increases = (st.session_state.optimization_results['Price Change %'] > 0).sum()
                    st.metric("Price Increases", f"{increases}/{len(results)}")
                with col3:
                    decreases = (st.session_state.optimization_results['Price Change %'] < 0).sum()
                    st.metric("Price Decreases", f"{decreases}/{len(results)}")
                
            except Exception as e:
                st.error(f"Error during optimization: {str(e)}")
                st.exception(e)

# Page: View Dashboard
elif page == "📊 View Dashboard":
    st.header("📊 Pricing Dashboard")
    
    if not st.session_state.optimization_complete:
        st.warning("⚠️ Please run price optimization first!")
        st.stop()
    
    # Get results
    df = st.session_state.optimization_results
    
    # Price comparison chart
    st.subheader("💰 Current vs Recommended Prices")
    
    fig_price = go.Figure()
    fig_price.add_trace(go.Bar(
        name='Current Price',
        x=df['Product Name'],
        y=df['Current Price'],
        marker_color='lightblue'
    ))
    fig_price.add_trace(go.Bar(
        name='Recommended Price',
        x=df['Product Name'],
        y=df['Recommended Price'],
        marker_color='darkblue'
    ))
    fig_price.update_layout(
        barmode='group',
        xaxis_tickangle=-45,
        height=500
    )
    st.plotly_chart(fig_price, use_container_width=True)
    
    # Price change percentage
    st.subheader("📈 Price Change Percentage")
    
    fig_change = px.bar(
        df,
        x='Product Name',
        y='Price Change %',
        color='Price Change %',
        color_continuous_scale='RdYlGn',
        title="Price Change by Product"
    )
    fig_change.update_layout(xaxis_tickangle=-45, height=400)
    st.plotly_chart(fig_change, use_container_width=True)
    
    # Detailed table
    st.subheader("📋 Detailed Results")
    
    # Format the dataframe for display
    display_df = df.copy()
    display_df['Current Price'] = display_df['Current Price'].apply(lambda x: f"€{x:.2f}")
    display_df['Recommended Price'] = display_df['Recommended Price'].apply(lambda x: f"€{x:.2f}")
    display_df['Avg Competitor Price'] = display_df['Avg Competitor Price'].apply(lambda x: f"€{x:.2f}")
    display_df['Price Change %'] = display_df['Price Change %'].apply(lambda x: f"{x:.1f}%")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Download button
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Results (CSV)",
        data=csv,
        file_name=f"price_recommendations_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

# Page: Analysis
elif page == "📈 Analysis":
    st.header("📈 Market Analysis")
    
    if not st.session_state.data_uploaded:
        st.warning("⚠️ Please upload data first!")
        st.stop()
    
    # Category analysis
    st.subheader("📦 Category Analysis")
    
    # Aggregate data by category
    category_data = []
    for file_name, df in st.session_state.scraper_data.items():
        if file_name not in ['overview', 'mapping'] and 'price' in df.columns:
            category = file_name.replace('.csv', '').replace('_', ' ').title()
            prices = df['price'].dropna()
            if len(prices) > 0:
                category_data.append({
                    'Category': category,
                    'Avg Price': prices.mean(),
                    'Min Price': prices.min(),
                    'Max Price': prices.max(),
                    'Product Count': len(prices),
                    'Price Range': prices.max() - prices.min()
                })
    
    if category_data:
        cat_df = pd.DataFrame(category_data)
        
        # Visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = px.bar(
                cat_df,
                x='Category',
                y='Avg Price',
                title='Average Price by Category',
                color='Avg Price',
                color_continuous_scale='Viridis'
            )
            fig1.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            fig2 = px.scatter(
                cat_df,
                x='Product Count',
                y='Price Range',
                size='Avg Price',
                color='Category',
                title='Market Diversity Analysis',
                hover_data=['Category', 'Avg Price']
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Detailed category table
        st.subheader("📊 Category Statistics")
        cat_display = cat_df.copy()
        for col in ['Avg Price', 'Min Price', 'Max Price', 'Price Range']:
            cat_display[col] = cat_display[col].apply(lambda x: f"€{x:.2f}")
        
        st.dataframe(cat_display, use_container_width=True, hide_index=True)

# Page: Instructions
elif page == "ℹ️ Instructions":
    st.header("ℹ️ How to Use This System")
    
    st.markdown("""
    ## 🔄 Complete Workflow
    
    ### 1️⃣ Local Scraping (On Your Computer)
    
    ```bash
    # In your project folder
    python scraper.py
    ```
    
    This will:
    - Scrape competitor prices from all configured stores
    - Save CSV files in the `product_data/` folder
    - Take 10-30 minutes depending on categories
    
    ### 2️⃣ Prepare Upload
    
    **Option A - ZIP Method (Recommended):**
    1. Go to your project folder
    2. Select these items:
       - `product_data/` folder (entire folder)
       - `Dzukou_Pricing_Overview_With_Names - Copy.csv`
       - `product_data_mapping.csv`
       - `category_keywords.json` (optional)
    3. Right-click → "Compress" or "Send to ZIP"
    
    **Option B - Individual Files:**
    - Upload each CSV from `product_data/`
    - Upload the overview and mapping files separately
    
    ### 3️⃣ Upload to Cloud App
    
    1. Go to "Upload Data" page
    2. Choose your upload method
    3. Select your files
    4. Wait for confirmation
    
    ### 4️⃣ Optimize Prices
    
    1. Go to "Optimize Prices" page
    2. Review settings (optional)
    3. Click "Run Price Optimization"
    4. Wait for completion
    
    ### 5️⃣ Review Results
    
    1. View Dashboard - Visual analysis
    2. Analysis - Market insights
    3. Download CSV - For implementation
    
    ## 🔧 Troubleshooting
    
    **"File encoding error"**
    - The app handles multiple encodings automatically
    - If issues persist, save CSVs as UTF-8
    
    **"Missing data"**
    - Ensure all required files are uploaded
    - Check file names match exactly
    
    **"No prices found"**
    - Run scraper again
    - Check if sites have changed
    - Verify search terms in `category_keywords.json`
    
    ## 📅 Recommended Schedule
    
    - **Weekly**: Run scraper and update prices
    - **Monthly**: Review pricing strategy
    - **Quarterly**: Adjust categories and keywords
    
    ## 💡 Pro Tips
    
    1. **Save scraper results** - Keep historical data
    2. **Monitor competitors** - Add new stores as needed
    3. **Test prices** - Start with small changes
    4. **Track results** - Measure actual vs predicted
    
    ## 🆘 Need Help?
    
    - Check scraper logs for errors
    - Verify all files are present
    - Ensure stable internet for scraping
    - Contact support with error screenshots
    """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    Dzukou Dynamic Pricing System | Upload-Based Architecture
    </div>
    """,
    unsafe_allow_html=True
)
