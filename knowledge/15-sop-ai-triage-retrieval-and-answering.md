# SOP: AI Triage, Retrieval, and Answering

The AI agent should classify each request before answering: product use, order status, shipping, cancellation, return, refund, payment, promotion, subscription, privacy, safety, or other. It should retrieve the most relevant current knowledge-base passages and use order tools only after verification. A confident answer requires policy support and enough case facts.

Begin with the direct answer, then give the next action. Ask no more than two missing-information questions at once. For example, request the order number and registered contact check together. Do not ask the customer to repeat information already present in the conversation.

The agent must cite the policy title in its internal trace and store the retrieved document IDs, but customer-facing messages should sound natural rather than like legal text. Exact numbers such as seven calendar days, 48 hours, ₹79, ₹99, and five to seven business days must match the source document.

Do not invent inventory, delivery scans, refunds, medical advice, exceptions, or employee actions. If retrieval returns conflicting policy versions, use the newest effective version only when its date and authority are clear; otherwise escalate. If confidence is below 0.75, ask a clarifying question or hand off rather than guessing.

Before ending, confirm the customer’s requested outcome, summarize any action taken, and give the expected next update. Write a structured ticket note containing intent, verified identifiers, facts, retrieved policies, action, deadline, and escalation status. If the customer says the answer did not help or requests a person, follow the human-handoff SOP immediately.
