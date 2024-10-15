import requests
import json
import os
import time
import random  # For random sampling
import re  # For extracting valid numbers
from dotenv import load_dotenv

# Load the default .env file
load_dotenv()

# Retrieve the API key from the environment variable
api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("API key not found. Ensure it's correctly set in the .env file.")

# Paths to input files
questions_path = "/Users/matthew/Desktop/TBrain-AI/競賽資料集/dataset/preliminary/questions_example.json"
ground_truth_path = "/Users/matthew/Desktop/TBrain-AI/競賽資料集/dataset/preliminary/ground_truths_example.json"
output_file = "/Users/matthew/Desktop/TBrain-AI/output/ans.json"

# Load the questions
with open(questions_path, "r", encoding="utf-8") as f:
    questions = json.load(f)["questions"]

# Load the ground truths
with open(ground_truth_path, "r", encoding="utf-8") as f:
    ground_truths = json.load(f)["ground_truths"]

# Allowed categories (only process files from these categories)
ALLOWED_CATEGORIES = {"finance", "insurance"}

# Filter questions to include only those from allowed categories
filtered_questions = [q for q in questions if q["category"] in ALLOWED_CATEGORIES]

# Randomly select exactly 20 questions from the filtered list
if len(filtered_questions) < 20:
    raise ValueError("Not enough questions from allowed categories to sample 20 questions.")
sampled_questions = random.sample(filtered_questions, 20)

# Base path for output files (where the .txt files are located)
output_base_path = "/Users/matthew/Desktop/TBrain-AI/output/"

def read_txt_file(filepath):
    """Reads a .txt file if it exists."""
    if not os.path.exists(filepath):
        print(f"Warning: File not found at {filepath}. Skipping...")
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def query_chatgpt(prompt):
    """Queries the ChatGPT API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional assistant. Provide only the most relevant source number."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error querying ChatGPT API: {e}")
        return "None"

def extract_source_number(response):
    """Extract the first valid integer from the response."""
    match = re.search(r'\b\d+\b', response)
    if match:
        return int(match.group(0))  # Convert the first number found to an integer
    return None  # Return None if no number is found

# Collect results
results = []

# Process the 20 sampled questions
for question in sampled_questions:
    query = question["query"]
    sources = question["source"]
    category = question["category"]

    print(f"\nProcessing QID: {question['qid']} - {query}")

    # Combine content from relevant .txt files
    combined_text = ""
    for pid in sources:
        txt_path = os.path.join(output_base_path, category, f"{pid}.txt")
        content = read_txt_file(txt_path)
        if content:
            combined_text += f"Source {pid}: {content}\n\n"

    prompt = (
        f"Question: {query}\n\n"
        f"Below are the relevant sources. Identify the source number that best answers the question:\n\n"
        f"{combined_text}\n\n"
        f"Please respond ONLY with the source number (e.g., 392). If no relevant source applies, respond with 'None'."
    )

    best_source = query_chatgpt(prompt)
    print(f"Best source for QID {question['qid']}: {best_source}")

    # Extract the source number from the response
    source_number = extract_source_number(best_source)

    if source_number is not None:
        results.append({"qid": question["qid"], "retrieve": source_number, "category": category})
    else:
        print(f"Invalid response for QID {question['qid']}. Setting retrieve to 'None'.")
        results.append({"qid": question['qid'], "retrieve": "None", "category": category})

    # Log invalid responses for debugging
    if source_number is None:
        with open("invalid_responses.log", "a") as log_file:
            log_file.write(f"QID {question['qid']} - Response: {best_source}\n")

    # Add a delay to avoid hitting API rate limits
    time.sleep(2)

# Save results to JSON
with open(output_file, "w", encoding="utf-8") as f:
    json.dump({"answers": results}, f, ensure_ascii=False, indent=4)

print(f"\nAll answers have been saved to {output_file}")

# Calculate accuracy by comparing predictions with ground truths
correct = 0
total = 0

for result in results:
    qid = result["qid"]
    predicted_retrieve = result["retrieve"]

    # Find the corresponding ground truth for this QID
    ground_truth = next((gt for gt in ground_truths if gt["qid"] == qid), None)

    if ground_truth:
        total += 1
        if predicted_retrieve == ground_truth["retrieve"]:
            correct += 1

accuracy = correct / total if total > 0 else 0
print(f"Accuracy: {accuracy:.2%}")
