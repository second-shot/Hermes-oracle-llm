from llama_cpp import Llama
import os

MODEL_PATH = "models/model.gguf"

llm = None

def load_model():
    global llm
    if llm is None:
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_threads=4,   # M1 safe setting
            n_batch=128,
            verbose=False
        )
    return llm

def build_messages(prompt):
    task = prompt["task"]["goal"]
    memory = prompt.get("memory", {})
    system_msg = "You are Hermes execution engine.\n\nRULES:\n- be concise\n- follow instruction exactly\n- deterministic output"
    user_msg = f"TASK:\n{task}\n\nMEMORY:\n{memory}"
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]

def call_model(prompt, route, config):
    if route != "local":
        return {"error": "cloud_not_enabled_in_m1_mode"}
    
    model = load_model()
    messages = build_messages(prompt)
    
    # Use chat completion
    output = model.create_chat_completion(
        messages,
        max_tokens=200,
        temperature=0.2
    )
    
    text = output['choices'][0]['message']['content'].strip()
    
    return {
        "result": text
    }