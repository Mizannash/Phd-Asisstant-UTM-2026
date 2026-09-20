import streamlit as st
import os
import sys
from dotenv import load_dotenv

# Add src/ to sys.path so we can import from main
sys.path.append(os.path.dirname(__file__))
from src.main import run_crew_pipeline

def init_page():
    st.set_page_config(
        page_title="CrewAI Research Assistant",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Load environment variables in case they exist
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path)

def main():
    import streamlit as st
    if "storage_pulled" not in st.session_state:
        try:
            from src.core.storage import StorageHandler
            StorageHandler.pull_state()
        except Exception as e:
            print(f"Failed to pull state on start: {e}")
        st.session_state.storage_pulled = True
        
    init_page()
    
    st.title("🎓 CrewAI PhD Research Assistant")
    st.markdown("Automated literature review pipeline powered by Gemini & OpenAlex.")

    # Sidebar for Settings
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key handling
        env_api_key = os.getenv("GEMINI_API_KEY", "")
        api_key = st.text_input(
            "Gemini API Key",
            value=env_api_key,
            type="password",
            help="Enter your Google Gemini API key. If it's in your .env file, it will load automatically."
        )
        
        st.divider()
        st.header("🛠️ Processing Mode")
        mode = st.radio(
            "Select Pipeline Mode:",
            ["Standard Mode", "Supervisor Mode"],
            help="Supervisor Mode tags the paper as high-priority before sending it to the Systematic Reviewer."
        )
        mode_val = "supervisor" if mode == "Supervisor Mode" else "standard"
        
        st.divider()
        st.markdown("**Agents:**")
        st.markdown("- 🧠 **Systematic Reviewer**: Filters for Kolej Vokasional relevance, formats APA 7 & Synthesizes quotes.")

    # Main content area
    st.subheader("📚 Process New Literature")
    paper_input = st.text_area(
        "Paste Paper Abstract or Title:",
        height=200,
        placeholder="Enter the abstract, title, or search results of the paper you want the agents to analyze..."
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        run_button = st.button("🚀 Run AI Pipeline", type="primary", use_container_width=True)
    with col2:
        save_to_file = st.checkbox("Also append result to `output/library.md`", value=True)
        
    st.divider()
    
    if run_button:
        if not api_key:
            st.error("⚠️ Please provide a Gemini API Key in the sidebar.")
            return
            
        if not paper_input.strip():
            st.warning("⚠️ Please provide a paper abstract or title to process.")
            return
            
        with st.status("🤖 AI Pipeline Running...", expanded=True) as status:
            try:
                st.write("Initializing Agents (M1 & M2)...")
                # Run the pipeline
                result = run_crew_pipeline(paper_text=paper_input, mode=mode_val, api_key=api_key)
                
                status.update(label="✅ Pipeline Complete!", state="complete", expanded=False)
                
                # Display Results
                st.subheader("📝 Systematic Reviewer's Synthesis")
                st.markdown(result)
                
                # Optionally save to file
                if save_to_file:
                    base_dir = os.path.dirname(os.path.dirname(__file__))
                    output_file = os.path.join(base_dir, "output", "library.md")
                    
                    # Create directory if it doesn't exist (just in case)
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    
                    try:
                        with open(output_file, "a", encoding="utf-8") as f:
                            f.write(f"\n\n## Entry (Mode: {mode_val} via Web UI)\n")
                            f.write(f"**Input:** {paper_input[:200]}...\n\n")
                            f.write(result)
                        st.success(f"Result successfully appended to `output/library.md`")
                    except Exception as e:
                        st.error(f"Failed to save to library.md: {str(e)}")
                        
                # Download Button for individual result
                st.download_button(
                    label="📥 Download this result as Markdown",
                    data=result,
                    file_name="literature_synthesis.md",
                    mime="text/markdown"
                )
                
            except Exception as e:
                status.update(label="❌ Pipeline Failed", state="error", expanded=True)
                st.error(f"An error occurred during execution: {str(e)}")

if __name__ == "__main__":
    main()

# Trigger hot-reload 2
