---
title: Agentic Engineering
source_url: https://app.notion.com/p/Agentic-Engineering-36da896bb9b68068971cdedbc6f37a42
notion_id: 36da896b-b9b6-8068-971c-dedbc6f37a42
category: Session Recordings
---

# Agentic Engineering

Reach Capital Session Recordings

**Date:** 2026-02-27
**Tags:** AI, engineering, product
**Recording:** [Recording link](https://us02web.zoom.us/rec/share/tJpnE7rBIriZ3WkuaVIyaBsHI3lcDWvrMq3hMD5WDs5afUP32gkMYYhm37_Jk2fO.cUCa0iZqEo_H65Cg?startTime=1772215397000)
Passcode: #9!Dk2uR
**Org:** Superconductor
**Speaker:** [Arjun Singh](https://www.linkedin.com/in/arjun-singh-629216105/)

1. Why Agentic Engineering Matters Now
- We’re in a shift from “engineers typing code in an IDE” to “engineers managing fleets of AI agents that write and test code.”
- Many teams have adopted tools like Cursor/Copilot, but:
  - Work still runs on one person’s laptop.
  - Agents get blocked waiting for humans to run apps, tests, and reviews.
- The opportunity: move from assistive AI on a laptop to background agents in the cloud so more work happens in parallel.
2. What Superconductor Does (In Plain Terms)
- Think of Superconductor as “GitHub + AI agents + preview environments”:
- Spins up cloud environments that can run your real app (including legacy and Dockerized apps).
- Lets you assign feature requests or bug fixes to AI agents, which then:
  - Read your codebase and instructions.
  - Make changes.
  - Run and test the app.
- You can see and interact with what the agent built in the browser without pulling code locally.
3. How Teams Use It Day‑to‑Day
- Creating work: Tickets get created from Slack messages (“make this sidebar resizable”), support emails, meeting transcripts (the bot listens and turns ideas into tickets).
- Who can start work: PMs, support, and even non‑technical teammates can describe what they want in natural language.
  - Engineers still step in for review and refinement, but avoid a lot of the busywork.
- Parallel work: For harder features, teams often
  - Run multiple agents in parallel on the same ticket.
  - Compare their outputs (screenshots, behavior), then pick the best one to polish and ship.
4. How Quality & Cost Stay Under Control
- Human still in the loop: Every change is reviewed before merging—this is not “ship whatever the AI wrote.”
- Superconductor has a guided review mode that:
  - Summarizes what changed and why.
  - Walks you through files in a logical order.
  - Lets you leave comments that go straight back to the agent to fix.
- Model choice & cost:
  - Different models (Claude, OpenAI, etc.) are benchmarked on your actual codebase for quality, speed, and cost.
  - Heavy work usually runs on individual model plans (e.g., Claude/Cursor subscriptions), so sticker‑price token costs are often covered there.
  - Lighter work can fall back to shared API keys.
5. What You Need for This to Work
- Your app must be runnable in a repeatable way (ideally in a Docker or similar setup so the same environment can spin up in the cloud)
- You need a shared setup for agents:
  - Common instructions (e.g., an Agents.md), coding standards, and tools.
  - Avoid a situation where half the team uses Cursor one way, others use different tools with conflicting rules.
- Cultural readiness:
  - Engineers treat agents as junior collaborators:
  - Let them draft, explore options, and run experiments.
6. What This Means for Founders & Teams
- Smaller teams can ship more (One full‑stack engineer plus strong agents can cover what used to take a larger team.)
- Product taste rises in importance: The hard part shifts from “can we build it?” to “what should we build and how should it feel?”
- Early adopters get a speed advantage:
  - Faster iteration cycles on features, bugs, and experiments.
  - More surface area covered (e.g., support‑driven fixes, small UX wins) without blowing up headcount.
### Transcript
  # Reach AMA: Agentic Engineering (Arjun Singh & Sergey Karayev, Superconductor) — Full Transcript & Notes

## AI-Generated Chapter Summaries


**[00:00:00.000 – 00:04:42.740] Agentic Coding: The Future of Dev**
Arjun and Sergey, who previously founded Greatscope, shared insights on the evolving landscape of software engineering, particularly focusing on the transition to agentic coding. They highlighted the efficiency of using AI agents for coding and discussed how developers are adapting to this new paradigm. The session was structured to cover both the broader implications of this shift and a demonstration of their product, Superconductor, which aims to streamline the process of building software using agent-based technologies. Participants were encouraged to ask questions and share their experiences with AI adoption in software development.


**[00:04:42.740 – 00:10:00.490] Transition to Parallel Agent Operations**
Arjun discussed the shift from writing code in IDEs to using background agents, highlighting the need to move from single-machine work to parallel agent operations. He explained how teams can leverage various signals, such as bug trackers and sales calls, to trigger autonomous work. Arjun demonstrated the use of Superconductor, a tool integrated with Slack and GitHub, to manage tasks and work with different models. He emphasized the importance of reviewing agent changes efficiently and suggested using multiple agents to explore different solutions simultaneously.


**[00:10:00.490 – 00:14:19.690] Ruby on Rails Production Deployment**
  The team discussed the development and deployment of a Ruby on Rails app running in Docker containers, emphasizing its production readiness and the ability to deploy the same version used in development. Arjun explained their goal of bringing a "vibe coding" experience to production-grade apps, allowing live editing and immediate results while maintaining rigorous code review processes. Sergey demonstrated a new voice input feature built by the agent, which has not yet been merged due to the need for style adjustments. Tony addressed questions about tokens and costs, clarifying that users can bring their own tokens and that Superconductor operates on a team-based workspace model, allowing developers to use their own plans for ticket implementations.


**[00:14:19.690 – 00:18:07.780] Cloud Coda and Kodak Plans**
Arjun explained how Cloud Coda and Kodak plans are used effectively within budget constraints, noting that while costs appear high, they are often covered by plan allocations rather than actual charges. Sergey addressed questions about using Claude, Max, or Pro accounts through Superconductor, clarifying that while Anthropic had concerns about OpenCode impersonating Claude, using Cloud Code directly is acceptable as long as it doesn't violate OpenAI's terms. Arjun demonstrated how multiple agents can be launched for complex tasks, showing an example where AMP produced a less refined waveform compared to Codex's output.


**[00:18:07.780 – 00:23:02.450] AI Agents for Design Exploration**
  Arjun discussed the use of AI agents for prototyping and design, emphasizing the trade-off between detailed specifications and allowing agents to explore ideas independently. He highlighted the benefits of a team workspace where non-technical team members can contribute to bug fixes and feature improvements through prompts. Esteban asked about the agents' ability to understand and question instructions, particularly in ideation and planning stages, to which Arjun explained that agents can provide implications and suggestions based on how tickets are worded. Tony mentioned a question from Ryan about planning, inviting Ryan to elaborate, but the transcript ended before Ryan could respond.


**[00:23:02.450 – 00:28:01.610] Interactive Planning and Agent Development**
The team discussed how to handle interactive planning and feature development with agents, with Arjun explaining that initial planning involves iterative conversations and adjustments before execution. They addressed concerns about scaling and managing dependencies across multiple teams, with Arjun suggesting the need for engineering discipline and manual task breakdown. Sergey concluded by discussing how to effectively reveal code through proper agent documentation and iteration, emphasizing the importance of writing detailed agent MD files to prevent common mistakes.


**[00:28:01.610 – 00:33:55.510] Superconductor Performance Evaluation Features**
  Arjun and Sergey discussed the features of Superconductor, focusing on making it easy to evaluate an agent's performance. They highlighted the guided review feature, which provides a high-level overview of code changes and allows for direct feedback on specific lines of code. Arjun explained that multiple team members can collaborate on a single thread, enhancing communication and feedback. They also mentioned that a significant portion of their work now originates from Slack, due to its convenience and the ability to leverage existing context.


**[00:33:55.510 – 00:37:21.040] New QA and Inbox Features**
The team discussed several upcoming features and improvements. Sergey mentioned a new QA Agent that will automatically test web applications using Playwright before sending them to human reviewers. Arjun introduced an inbox feature for projects that can process support emails and create tickets, with the team currently using it to manage their own support requests. The team also discussed a feature request from Amy for audio capabilities in guided reviews, and Adam inquired about plans for more adversarial review, though Sergey noted they are not ready to show this feature yet.


**[00:37:21.040 – 00:41:56.230] Autonomous Software Organizations Vision**
The team discussed a vision for autonomous software organizations where ideas from various sources can automatically trigger implementations. Sergey demonstrated how a meeting transcript was analyzed to create tickets and generate code, highlighting the potential for automated feature requests and bug fixes. Arjun and Sergey explained the safety measures of running code in sandboxes, including network restrictions and the need for human approval before merging changes. The discussion touched on the advantages of cloud-based development environments over local machines for agent security and control.


  **[00:41:56.230 – 00:48:16.560] AI Agent Performance Benchmarking Results**
The team discussed research on AI agent performance and code quality metrics. Arjun and Sergey presented benchmarking results showing that PVD 5.3 Codex outperformed Opus in both quality and speed, taking around 7-7.5 minutes per task compared to Opus's 12 minutes. Sergey shared preliminary findings on the effectiveness of agents.md files, noting that while they can be useful for specific coding guidelines, more research is needed to determine their overall impact on agent performance. The team also addressed questions about team composition and code quality measurement, with Arjun explaining that they use a rubric-based scoring system averaging results from Gemini, GPT-5 2, and Opus.


**[00:48:16.560 – 00:58:19.410] AI Agents in Software Development**
Arjun and Sergey discussed their approach to AI agents in software development, emphasizing that specialized roles and UI interactions are more effective than multi-agent swarms. They highlighted Superconductor's environment setup, which allows agents to start within 30 seconds using snapshots of Docker containers. The team is working on making code reviews more efficient, including an experimental feature to recommend which pull requests deserve attention. Arjun also shared that hiring full-stack engineers with strong product taste is crucial, and they are exploring ways to standardize AI usage across teams to avoid splits in adoption.
