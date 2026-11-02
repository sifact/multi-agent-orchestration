# types.py

Defines the agent contract: context in, reply out, and the Tool shape.

* AgentContext carries the model, database path, knowledge folder and step limit.
* AgentReply returns the answer with tokens, model time, retry wait, call counts and a tool trace.
* Tool wraps a function the model can call and renders its OpenAI tool spec.
* Plain frozen values keep handle() easy to wrap in a service for project 2.
* Agent modules may import this contract but never each other.
