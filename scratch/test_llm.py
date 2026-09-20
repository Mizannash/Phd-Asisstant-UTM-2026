import os
import sys
from dotenv import load_dotenv

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Load environment
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from quota_manager import QuotaManager
from crewai import Agent, Task, Crew, Process

def test_llm():
    print(f"Total API Keys configured: {QuotaManager.get_total_keys()}")
    
    def run_crew():
        # Set explicitly to Gemini 3.7 Flash using LiteLLM format
        test_agent = Agent(
            role='Test Agent',
            goal='Just say hello',
            backstory='A simple test agent.',
            llm="gemini/gemini-3.7-flash",
            verbose=True
        )
        test_task = Task(
            description='Say hello and report what model you think you are running on.',
            expected_output='A friendly greeting.',
            agent=test_agent
        )
        crew = Crew(
            agents=[test_agent],
            tasks=[test_task],
            process=Process.sequential
        )
        return crew.kickoff()

    try:
        print("Executing LLM Call...")
        result = QuotaManager.execute_call(run_crew)
        print("\n\n=== SUCCESS ===")
        print(f"Used API Key Index: {QuotaManager.get_active_key_index()}")
        print(f"Result:\n{result}")
    except Exception as e:
        print("\n\n=== FAILED ===")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm()
