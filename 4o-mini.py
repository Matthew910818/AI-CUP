import requests
import json
import os
import time
import re
import random
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")

questions_path = "/Users/matthew/Desktop/TBrain-AI/競賽資料集/dataset/preliminary/questions_example.json"
ground_truth_path = "/Users/matthew/Desktop/TBrain-AI/競賽資料集/dataset/preliminary/ground_truths_example.json"
output_file = "/Users/matthew/Desktop/TBrain-AI/output/ans.json"

with open(questions_path, "r", encoding="utf-8") as f:
    questions = json.load(f)["questions"]

with open(ground_truth_path, "r", encoding="utf-8") as f:
    ground_truths = json.load(f)["ground_truths"]

filtered_questions = [q for q in questions]

output_base_path = "/Users/matthew/Desktop/TBrain-AI/output/"

def read_txt_file(filepath):
    """Reads a .txt file if it exists."""
    if not os.path.exists(filepath):
        print(f"Warning: File not found at {filepath}. Skipping...")
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def extract_source_numbers(response):
    """Extract all valid integers from the response."""
    return [int(match.group(0)) for match in re.finditer(r'\b\d+\b', response)]

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
            {
                "role": "system",
                "content": "你是一個專業的助理。你的任務是根據提供的文章，找出所有可能包含問題答案的文章編號。"
                           "請務必閱讀所有提供的文章，並列出所有可能符合問題答案的文章編號，以逗號分隔。"
                           "有些問題需要透過閱讀理解前後文才能得到最佳答案。"
                           "即便文章提到相關主題，如果它沒有直接回答問題，則不要選擇該文章。"
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error querying ChatGPT API: {e}")
        return "None"

def requery_chatgpt(prompt):
    """Queries the ChatGPT API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "你是一個專業的助理。你的任務是根據提供的文章，找出最適合答案的文章編號。"
                           "請務必閱讀所有提供的文章，並提供答案的文章編號。"
                           "有些問題需要透過閱讀理解前後文才能得到最佳答案。"
                           "即便文章提到相關主題，如果它沒有直接回答問題，則不要選擇該文章。"
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error querying ChatGPT API: {e}")
        return "None"

def confirm_best_choice(possible_answers, category):
    """Query ChatGPT to pick the best answer from possible answers with full context."""
    full_context = ""
    for answer in possible_answers:
        txt_path = os.path.join(output_base_path, category, f"{answer}.txt")
        content = read_txt_file(txt_path)
        if content:
            full_context += (
                f"=== 文章 {answer} 開始 ===\n\n"
                f"{content}\n\n"
                f"=== 文章 {answer} 結束 ===\n\n"
            )
        else:
            full_context += f"=== 文章 {answer} 缺少內容 ===\n\n"

    confirmation_prompt = (
        f"以下是可能包含答案的文章編號及其內容：\n\n{full_context}\n"
        "請先檢查**全部**的文章，並根據內容選擇一個最符合問題的文章編號。\n\n\n"
        "請注意，你只能選擇並輸出**唯一一個**編號，不要列出多個編號或其他資訊，"
        "僅需輸出最符合問題的那個編號（只輸出一個編號）。"
    )
    return requery_chatgpt(confirmation_prompt)


def get_best_source_number(prompt, sources, category):
    """Query ChatGPT for possible answers and confirm the best one."""
    response = query_chatgpt(prompt)
    possible_answers = extract_source_numbers(response)
    print("Possible Answers = ", possible_answers)

    if not possible_answers:
        return None
    elif len(possible_answers) == 1:
        return possible_answers[0]
    else:
        best_answer_response = confirm_best_choice(possible_answers, category)
        print("Best Answer Response = ", best_answer_response)
        best_answer = extract_source_numbers(best_answer_response)
        print("Best Answer = ", best_answer)
        return best_answer[0] if best_answer else None

def query_for_explanation(prompt, predicted, ground_truth):
    """Queries ChatGPT for the reason why it didn't choose the ground truth."""
    if predicted == "None":
        explanation_prompt = (
            f"{prompt}\n\n你沒有選擇任何文章編號作為答案，但正確答案應該是文章編號 {ground_truth}。\n"
            "請解釋為什麼你沒有選擇任何文章，並說明該問題可能會導致這個結果的原因。"
        )
    else:
        explanation_prompt = (
            f"{prompt}\n\n你選擇了文章編號 {predicted} 作為答案，但正確答案應該是文章編號 {ground_truth}。\n"
            "請解釋為什麼你選擇了 {predicted} 而不是 {ground_truth}，並指出具體的原因。"
        )
    return query_chatgpt(explanation_prompt)

def query_review_phase(prompt, initial_selection, ground_truth):
    """Queries ChatGPT to review the initial selection against other articles."""
    if initial_selection == "None":
        review_prompt = (
            f"你沒有選擇任何文章編號作為答案，請檢查所有文章並確認是否有任何文章（例如 {ground_truth}）能提供更直接、具體的答案。\n"
            "如果你認為沒有文章能回答這個問題，請解釋原因。"
        )
    else:
        review_prompt = (
            f"你選擇了文章編號 {initial_selection} 作為答案，請再次檢查所有其他文章，"
            f"確認是否有其他文章（例如 {ground_truth}）能提供更直接、具體的答案。\n"
            "如果你認為最初的選擇是正確的，請解釋為什麼。"
        )
    return query_chatgpt(review_prompt)

results = []


for question in filtered_questions:
    query = question["query"]
    sources = question["source"]
    category = question["category"]

    print(f"\nProcessing QID: {question['qid']} - {query}")

    prompt = (
        f"=== 問題 ===\n"
        f"{query}\n\n"
    )

    for pid in sources:
        txt_path = os.path.join(output_base_path, category, f"{pid}.txt")
        content = read_txt_file(txt_path)
        if content:
            prompt += (
                f"=== 文章 {pid} 開始 ===\n\n"
                f"{content}\n\n"
                f"=== 文章 {pid} 結束 ===\n\n"
            )

    prompt += (
        "文章編號是隨機的，你必須回答最有可能找到具體答案的那個文章的編號，答案只有一個。\n\n\n"
        "請優先選擇提供具體答案的文章，而不是僅僅提及相關主題的文章。\n\n\n"
        "即便文章提到相關主題，如果它沒有直接回答問題，則不要選擇該文章。\n\n\n"
        "請在閱讀所有文章後，根據內容回答最有可能找到答案的文章編號，並優先選擇能夠明確解答問題的文章。\n\n\n"
        "請注意，只能在閱讀完所有文章後才能回答。\n\n\n"
        "你只需要輸出文章的編號，不需要輸出文章的內容，或其他無關的內容。只需要輸出文章編號即可。"
    )

    best_source_number = get_best_source_number(prompt, sources, category)
    print(f"Best source for QID {question['qid']}: {best_source_number}")

    if best_source_number is not None:
        results.append({"qid": question["qid"], "retrieve": best_source_number, "category": category})
    else:
        print(f"Invalid response for QID {question['qid']}. Setting retrieve to 'None'.")
        results.append({"qid": question["qid"], "retrieve": "None", "category": category})

    ground_truth = next((gt for gt in ground_truths if gt["qid"] == question['qid']), None)

    if ground_truth:
        if best_source_number != ground_truth["retrieve"]:
            explanation = query_for_explanation(prompt, best_source_number, ground_truth["retrieve"])
            print(f"\nQID: {question['qid']}")
            print(f"Predicted answer: {best_source_number}, Ground truth: {ground_truth['retrieve']}")
            print(f"Explanation of why the ground truth was not chosen: {explanation}")

            review_explanation = query_review_phase(prompt, best_source_number, ground_truth["retrieve"])
            print(f"Review explanation: {review_explanation}")

    time.sleep(3)

with open(output_file, "w", encoding="utf-8") as f:
    json.dump({"answers": results}, f, ensure_ascii=False, indent=4)

print(f"\nAll answers have been saved to {output_file}")

correct = 0
total = 0

for result in results:
    qid = result["qid"]
    predicted_retrieve = result["retrieve"]

    ground_truth = next((gt for gt in ground_truths if gt["qid"] == qid), None)

    if ground_truth:
        total += 1
        if predicted_retrieve == ground_truth["retrieve"]:
            correct += 1

accuracy = correct / total if total > 0 else 0
print(f"Accuracy: {accuracy:.2%}")
