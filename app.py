import streamlit as st
import json
import os
import math
import re # For parsing inch sizes and creating safe keys


# --- Configuration ---
JSON_FILE_PATH = "output_flange_data.json"
# Reference billet: 20ft 100x100mm weighs 482kg
REFERENCE_BILLET_WIDTH_MM = 100
REFERENCE_BILLET_HEIGHT_MM = 100
REFERENCE_BILLET_MASS_KG = 482.0
GST_RATE = 0.19  # 19%

# --- Helper Functions ---
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"Error: Data file not found at {file_path}")
        return None
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        st.error(f"Error: Could not decode JSON from {file_path}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while loading data: {e}")
        return None

def get_nested_value(data_dict, path_list):
    current_level = data_dict
    for key_part in path_list: # Renamed path to path_list for clarity
        if isinstance(current_level, dict) and key_part in current_level:
            current_level = current_level[key_part]
        else:
            return None
    return current_level

def calculate_billet_weight_from_section(section_str):
    if not section_str or 'x' not in section_str.lower(): return None
    try:
        parts = section_str.lower().split('x')
        if len(parts) != 2: return None
        width_mm, height_mm = float(parts[0]), float(parts[1])
        if REFERENCE_BILLET_WIDTH_MM == 0 or REFERENCE_BILLET_HEIGHT_MM == 0: return None # Avoid division by zero
        return (width_mm * height_mm * REFERENCE_BILLET_MASS_KG) / \
               (REFERENCE_BILLET_WIDTH_MM * REFERENCE_BILLET_HEIGHT_MM)
    except (ValueError, IndexError, TypeError): return None

def get_cutting_waste_kg(inch_size_str):
    if not inch_size_str: return 0.2
    numeric_inch_val = 0.0
    try:
        cleaned_inch_str = inch_size_str.replace('_inch', '').strip()
        parts = cleaned_inch_str.split('_')
        if len(parts) == 1: numeric_inch_val = float(parts[0])
        elif len(parts) == 2: numeric_inch_val = float(parts[0]) / float(parts[1])
        elif len(parts) == 3: numeric_inch_val = float(parts[0]) + (float(parts[1]) / float(parts[2]))
        else: numeric_inch_val = float(parts[0]) # Fallback
    except (ValueError, IndexError, TypeError): numeric_inch_val = 0
    if numeric_inch_val <= 0: return 0.2
    if numeric_inch_val <= 4: return 0.2
    elif numeric_inch_val <= 8: return 0.5
    elif numeric_inch_val <= 12: return 1.0
    else: return 1.0

def create_safe_key(description_str):
    return re.sub(r'\W+', '_', str(description_str))

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == "ranco123":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    return True

# --- Streamlit App ---
st.set_page_config(layout="wide")

if check_password():
    st.title("Flange Cost Calculator")
    flange_database = load_data(JSON_FILE_PATH)

    if flange_database:
        level_names = ["Flange Type", "Inch Size", "Class Rating", "Face/Schedule/(General)",
                       "Schedule/Section/(General)", "Section/Variant", "Variant/Description"]

        # Initialize session state for selections
        if 'selections' not in st.session_state:
            st.session_state.selections = [""] * len(level_names)

        # Initialize session state for all cost inputs and other persistent fields
        cost_input_keys_defaults = {
            "cost_steel_per_kg_input": 100.0, "scrap_cost_per_kg_input": 20.0,
            "machining_labour_cost_kg_input": 10.0, "forging_labour_cost_kg_input": 15.0,
            "transportation_cost_kg_input": 5.0, "profit_margin_percent_input": 10.0,
            "num_pieces_required_input": 1, "ft_manual_checkbox": False, "ft_manual_input": 0.0
        }
        for key, default_value in cost_input_keys_defaults.items():
            if key not in st.session_state: st.session_state[key] = default_value

        if 'extra_flange_prices' not in st.session_state:
            st.session_state.extra_flange_prices = {}

        def selection_on_change_callback(level_idx, widget_key_for_level):
            st.session_state.selections[level_idx] = st.session_state[widget_key_for_level]
            # When a selection changes, reset subsequent selections in session_state
            for k in range(level_idx + 1, len(st.session_state.selections)):
                st.session_state.selections[k] = ""
                # Also reset the corresponding selectbox widget state if it exists
                # This is more of a failsafe; Streamlit usually handles this if options change
                # and the old value is no longer valid.
                # However, explicitly clearing the widget's session state key can be more robust.
                # selectbox_key_to_clear = f"selectbox_level_{k}"
                # if selectbox_key_to_clear in st.session_state:
                #     st.session_state[selectbox_key_to_clear] = ""


        st.sidebar.header("1. Select Flange Specifications")

        # --- Dropdown rendering loop ---
        current_data_for_options = flange_database
        for i in range(len(level_names)):
            data_source_for_current_dropdown = flange_database
            for prev_level_idx in range(i):
                key_in_path = st.session_state.selections[prev_level_idx]
                if isinstance(data_source_for_current_dropdown, dict) and key_in_path in data_source_for_current_dropdown:
                    data_source_for_current_dropdown = data_source_for_current_dropdown[key_in_path]
                else:
                    data_source_for_current_dropdown = {}
                    break

            if isinstance(data_source_for_current_dropdown, dict) and \
               all(k in data_source_for_current_dropdown for k in ['FW', 'CW']):
                break

            options_for_this_level = [""]
            if isinstance(data_source_for_current_dropdown, dict):
                options_for_this_level.extend(list(data_source_for_current_dropdown.keys()))

            selectbox_widget_key = f"selectbox_level_{i}"
            current_selection_value = st.session_state.selections[i]

            # Ensure current_selection_value is valid for the current options_for_this_level
            if current_selection_value not in options_for_this_level:
                st.session_state.selections[i] = "" # Reset if invalid
                current_selection_value = ""

            try:
                current_idx = options_for_this_level.index(current_selection_value)
            except ValueError:
                current_idx = 0 # Default to blank if somehow still not found (should be caught above)

            st.sidebar.selectbox(
                f"Select {level_names[i]}:",
                options_for_this_level,
                index=current_idx,
                key=selectbox_widget_key,
                on_change=selection_on_change_callback,
                args=(i, selectbox_widget_key)
            )

        # --- Derive selected_flange_data and extra flanges based on current st.session_state.selections ---
        active_selection_path = [s for s in st.session_state.selections if s]
        selected_flange_data = None
        if active_selection_path:
            data_candidate = get_nested_value(flange_database, active_selection_path)
            if isinstance(data_candidate, dict) and all(k in data_candidate for k in ['FW', 'CW']):
                selected_flange_data = data_candidate

        identified_extra_flanges = []
        primary_flange_description_for_display = ""
        if selected_flange_data and active_selection_path:
            final_key_part = active_selection_path[-1]
            if isinstance(final_key_part, str):
                parts = re.split(r'\s*\+\s*', final_key_part)
                if parts:
                    primary_flange_description_for_display = parts[0].strip()
                    if len(parts) > 1:
                        identified_extra_flanges = [part.strip() for part in parts[1:] if part.strip()]
            else:
                primary_flange_description_for_display = str(final_key_part)

            new_extra_flange_prices = {}
            for desc in identified_extra_flanges:
                price_key = f"price_extra_{create_safe_key(desc)}"
                if price_key not in st.session_state:
                    st.session_state[price_key] = 0.0
                new_extra_flange_prices[desc] = st.session_state[price_key]
            st.session_state.extra_flange_prices = new_extra_flange_prices

        # --- Costing Inputs Sidebar Section (Moved Here) ---
        st.sidebar.header("2. Enter Costing Inputs")
        st.sidebar.number_input("Cost of Steel (per kg of CW):", min_value=0.01, step=0.01, format="%.2f", key="cost_steel_per_kg_input")
        st.sidebar.number_input("Scrap Value (per kg):", min_value=0.0, step=0.01, format="%.2f", key="scrap_cost_per_kg_input")
        st.sidebar.number_input("Machining Labour (per kg of CW):", min_value=0.0, step=0.1, format="%.2f", key="machining_labour_cost_kg_input")
        st.sidebar.number_input("Forging Labour (per kg of CW):", min_value=0.0, step=0.1, format="%.2f", key="forging_labour_cost_kg_input")
        st.sidebar.number_input("Transportation (per kg of FT/CW):", min_value=0.0, step=0.1, format="%.2f", key="transportation_cost_kg_input")
        st.sidebar.number_input("Desired Profit Margin (% on cost):", min_value=0.0, max_value=200.0, step=0.5, format="%.1f", key="profit_margin_percent_input")
        st.sidebar.number_input("Number of Pieces Required:", min_value=1, step=1, key="num_pieces_required_input")

        if identified_extra_flanges:
            st.sidebar.subheader("Extra Flange Selling Prices")
            for extra_flange_desc in identified_extra_flanges:
                price_key = f"price_extra_{create_safe_key(extra_flange_desc)}"
                st.sidebar.number_input(f"Price for: {extra_flange_desc}", min_value=0.0, step=0.01, format="%.2f", key=price_key)
                if price_key in st.session_state: # Ensure key exists if widget just created it
                     st.session_state.extra_flange_prices[extra_flange_desc] = st.session_state[price_key]


        st.header("Selected Flange Details")
        if selected_flange_data:
            display_path_parts = active_selection_path[:]
            if display_path_parts and identified_extra_flanges:
                display_path_parts[-1] = primary_flange_description_for_display if primary_flange_description_for_display else "(Main item)"
            display_path_str = " -> ".join(display_path_parts)
            st.write(f"**Path to Costed Item:** {display_path_str}")

            if identified_extra_flanges:
                st.write("**Additional flanges produced (enter selling prices in sidebar):**")
                for extra_desc in identified_extra_flanges: st.write(f"- {extra_desc}")
            st.json(selected_flange_data)

            cw_flange = selected_flange_data.get("CW")
            fw_flange = selected_flange_data.get("FW")
            ft_flange_from_data = selected_flange_data.get("FT")
            section_from_data = selected_flange_data.get("SECTION", "N/A")
            inch_size_selected_str = active_selection_path[1] if len(active_selection_path) > 1 else ""

            if cw_flange is None or fw_flange is None:
                st.error("Critical CW or FW data is missing for the selected path. Cannot proceed.")
            else:
                # FT manual input section remains conditional on selected_flange_data
                ft_flange_final = ft_flange_from_data
                if ft_flange_from_data is None or not isinstance(ft_flange_from_data, (int, float)):
                    st.sidebar.markdown(f"<small>Note: FT in data is '{ft_flange_from_data}'.</small>", unsafe_allow_html=True)
                    st.sidebar.checkbox("Provide FT manually for scrap & transportation?", key="ft_manual_checkbox")
                    if st.session_state.ft_manual_checkbox:
                        suggested_ft_for_manual = float(fw_flange) * 0.9 if fw_flange is not None else 0.0
                        st.sidebar.number_input(
                            f"FT per piece (kg) (FW is {fw_flange:.2f} kg, e.g., {suggested_ft_for_manual:.2f} kg):",
                            min_value=0.0, step=0.01, format="%.2f", key="ft_manual_input"
                        )
                        ft_flange_final = st.session_state.ft_manual_input
                
                if st.button("Calculate Costs", key="calc_button"):
                    calc_cost_steel_per_kg = st.session_state.cost_steel_per_kg_input
                    calc_scrap_cost_per_kg = st.session_state.scrap_cost_per_kg_input
                    calc_machining_labour = st.session_state.machining_labour_cost_kg_input
                    calc_forging_labour = st.session_state.forging_labour_cost_kg_input
                    calc_transportation_cost = st.session_state.transportation_cost_kg_input
                    calc_profit_margin = st.session_state.profit_margin_percent_input
                    calc_num_pieces = st.session_state.num_pieces_required_input

                    st.header("Calculation Results")
                    st.write(f"**Costing for Primary Flange:** {display_path_str}")
                    st.write(f"  **CW:** {cw_flange:.3f} kg, **FW:** {fw_flange:.3f} kg, **FT (used):** {ft_flange_final if ft_flange_final is not None and isinstance(ft_flange_final, (int,float)) else 'N/A'} kg, **Section:** {section_from_data}")

                    st.subheader("1. Material & Billet Details")
                    calculated_billet_mass_kg = calculate_billet_weight_from_section(section_from_data)
                    cutting_waste_kg_per_piece = get_cutting_waste_kg(inch_size_selected_str)
                    if calculated_billet_mass_kg: st.metric(label=f"Calculated Billet Mass (for {section_from_data} section)", value=f"{calculated_billet_mass_kg:.2f} kg")
                    else: st.warning(f"Could not calculate billet mass for section: {section_from_data}.")
                    st.metric(label=f"Cutting Waste per Piece (for {inch_size_selected_str})", value=f"{cutting_waste_kg_per_piece:.3f} kg")
                    material_consumed_per_piece_kg = cw_flange + cutting_waste_kg_per_piece
                    if calculated_billet_mass_kg and material_consumed_per_piece_kg > 0:
                        num_pieces_from_billet_calc = calculated_billet_mass_kg / material_consumed_per_piece_kg
                        st.metric(label="Material Input per Piece (CW + Waste)", value=f"{material_consumed_per_piece_kg:.3f} kg")
                        st.metric(label=f"Pieces from one Billet", value=f"{num_pieces_from_billet_calc:.2f} (approx. {math.floor(num_pieces_from_billet_calc)} complete)")
                    elif material_consumed_per_piece_kg > 0: st.metric(label="Material Input per Piece (CW + Waste)", value=f"{material_consumed_per_piece_kg:.3f} kg")
                    else: st.warning("Cannot calculate pieces from billet.")

                    st.subheader("2. Cost Breakdown per Piece")
                    steel_cost_per_piece = cw_flange * calc_cost_steel_per_kg
                    st.metric(label="Steel Cost per Piece", value=f"₹{steel_cost_per_piece:.2f}")
                    machining_cost_per_piece = calc_machining_labour * cw_flange
                    st.metric(label="Machining Labour per Piece", value=f"₹{machining_cost_per_piece:.2f}")
                    forging_cost_per_piece = calc_forging_labour * cw_flange
                    st.metric(label="Forging Labour per Piece", value=f"₹{forging_cost_per_piece:.2f}")

                    transportation_weight_basis_kg = cw_flange
                    transportation_basis_label = "(based on CW as FT not available/provided)"
                    if ft_flange_final is not None and isinstance(ft_flange_final, (int, float)):
                        transportation_weight_basis_kg = ft_flange_final
                        transportation_basis_label = "(based on FT)"
                    transportation_cost_per_piece = calc_transportation_cost * transportation_weight_basis_kg
                    st.metric(label=f"Transportation per Piece {transportation_basis_label}", value=f"₹{transportation_cost_per_piece:.2f}")

                    scrap_value_per_piece = 0.0; scrap_loss_factor = 0.90
                    if ft_flange_final is not None and isinstance(ft_flange_final, (int, float)) and fw_flange is not None:
                        scrap_generated_kg_per_piece_gross = 0.0
                        if fw_flange < ft_flange_final: st.warning(f"FW ({fw_flange:.3f} kg) < FT ({ft_flange_final:.3f} kg). Scrap is 0 kg.")
                        else: scrap_generated_kg_per_piece_gross = fw_flange - ft_flange_final
                        recoverable_scrap_kg_per_piece = scrap_generated_kg_per_piece_gross * scrap_loss_factor
                        scrap_value_per_piece = recoverable_scrap_kg_per_piece * calc_scrap_cost_per_kg
                        st.metric(label="Gross Scrap Generated (FW-FT)", value=f"{scrap_generated_kg_per_piece_gross:.3f} kg")
                        st.metric(label=f"Recoverable Scrap (after {(1-scrap_loss_factor)*100:.0f}% loss)", value=f"{recoverable_scrap_kg_per_piece:.3f} kg")
                        st.metric(label="Scrap Value per Piece", value=f"₹{scrap_value_per_piece:.2f}")
                    else: st.write("Scrap value (FW-FT) not calculated as FT was not available/provided or FT was invalid.")

                    total_value_from_extra_flanges = 0.0
                    if st.session_state.extra_flange_prices and identified_extra_flanges:
                        st.write("**Income from Extra Flanges:**")
                        for desc in identified_extra_flanges:
                            price = st.session_state.extra_flange_prices.get(desc, 0.0)
                            st.write(f"- Selling '{desc}': ₹{price:.2f}")
                            total_value_from_extra_flanges += price
                        if total_value_from_extra_flanges > 0:
                             st.metric(label="Total Income from Extra Flanges", value=f"₹{total_value_from_extra_flanges:.2f}")

                    total_cost_per_piece_before_profit = (steel_cost_per_piece + machining_cost_per_piece +
                                                         forging_cost_per_piece + transportation_cost_per_piece -
                                                         scrap_value_per_piece - total_value_from_extra_flanges)
                    st.metric(label="Total Cost per Piece (Before Profit & GST)", value=f"₹{total_cost_per_piece_before_profit:.2f}", delta_color="inverse")

                    st.subheader("3. Final Pricing per Piece")
                    profit_amount_per_piece = total_cost_per_piece_before_profit * (calc_profit_margin / 100.0)
                    st.metric(label=f"Profit per Piece ({calc_profit_margin:.1f}%)", value=f"₹{profit_amount_per_piece:.2f}")
                    cost_with_profit_per_piece = total_cost_per_piece_before_profit + profit_amount_per_piece
                    st.metric(label="Cost with Profit per Piece", value=f"₹{cost_with_profit_per_piece:.2f}")
                    gst_amount_per_piece = cost_with_profit_per_piece * GST_RATE
                    st.metric(label=f"GST per Piece ({GST_RATE*100:.0f}%)", value=f"₹{gst_amount_per_piece:.2f}")
                    final_selling_price_per_piece = cost_with_profit_per_piece + gst_amount_per_piece
                    st.success(f"**Final Selling Price per Piece (Incl. GST): ₹{final_selling_price_per_piece:.2f}**")

                    st.subheader(f"4. Total Order Value for {calc_num_pieces} Pieces")
                    total_order_value = final_selling_price_per_piece * calc_num_pieces
                    st.info(f"**Total Order Value: ₹{total_order_value:.2f}**")
        else:
            st.info("Select flange specifications from the sidebar to see details and calculate costs. If selections are made but no details appear, the chosen combination may be invalid or incomplete.")
    else:
        st.error("Could not load flange data. Please ensure 'output_flange_data.json' is in the correct location and format.")
