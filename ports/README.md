# ports/

**What belongs here.** Six interfaces and their adapters: storage, delivery, secrets, queue, llm. Each port has a Protocol and a conformance suite every adapter must pass.

**What does not.** Nothing outside this package imports a concrete adapter.
