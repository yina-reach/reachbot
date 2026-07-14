---
title: https://docs.anthropic.com/claude/docs/models-overview
source_url: https://docs.anthropic.com/claude/docs/models-overview
notion_source: Anthropic
---

If you're unsure which model to use, consider starting with Claude Opus 4.8 for the most complex tasks. It is Anthropic's most capable Opus-tier model for complex reasoning, long-horizon agentic coding, and high-autonomy work. For workloads that need the highest available capability, see Claude Fable 5.
All current Claude models support text and image input, text output, multilingual capabilities, and vision. Models are available through the Claude API, Claude Platform on AWS, Amazon Bedrock, Vertex AI, and Microsoft Foundry.
Once you've picked a model, learn how to make your first API call.
Claude Fable 5 (claude-fable-5) is Anthropic's most capable widely released model. Claude Mythos 5 (claude-mythos-5) joins the invitation-only Claude Mythos Preview (claude-mythos-preview) within Project Glasswing. See Introducing Claude Fable 5 and Claude Mythos 5 for launch details and API changes.
| Feature | Claude Fable 5 | Claude Mythos 5 | 
|---|---|---|
| Description | Anthropic's most capable widely released model, for the most demanding reasoning and long-horizon agentic work | Available through Project Glasswing. Successor to Claude Mythos Preview. | 
| Claude API ID | claude-fable-5 | claude-mythos-5 | 
| AWS Bedrock ID | anthropic.claude-fable-5 | Limited availability | 
| Vertex AI ID | claude-fable-5 | Limited availability | 
| Extended thinking | No | No | 
| Adaptive thinking | Yes (always on) | Yes (always on) | 
| Context window | 1M tokens | 1M tokens | 
Claude Fable 5 is generally available on the Claude API, Claude Platform on AWS, Amazon Bedrock, Vertex AI, and Microsoft Foundry beginning June 9, 2026. Claude Mythos 5 is not generally available: it is offered in limited availability to approved customers in Project Glasswing, beginning the same day. For access, contact your Anthropic, AWS, or Google Cloud account team.
| Feature | Claude Opus 4.8 | Claude Sonnet 4.6 | Claude Haiku 4.5 | 
|---|---|---|---|
| Description | Anthropic's most capable Opus-tier model for complex reasoning and agentic coding | The best combination of speed and intelligence | The fastest model with near-frontier intelligence | 
| Claude API ID | claude-opus-4-8 | claude-sonnet-4-6 | claude-haiku-4-5-20251001 | 
| Claude API alias | claude-opus-4-8 | claude-sonnet-4-6 | claude-haiku-4-5 | 
| AWS Bedrock ID | anthropic.claude-opus-4-83 | anthropic.claude-sonnet-4-6 | anthropic.claude-haiku-4-5-20251001-v1:0 | 
| Vertex AI ID | claude-opus-4-8 | claude-sonnet-4-6 | claude-haiku-4-5@20251001 | 
1 - See Pricing for complete pricing information including Batch API discounts and prompt caching rates.
2 - Reliable knowledge cutoff indicates the date through which a model's knowledge is most extensive and reliable. Training data cutoff is the broader date range of training data used. For more information, see Anthropic's Transparency Hub.
3 - Claude Opus 4.8 is available on Bedrock through Claude in Amazon Bedrock (the Messages-API Bedrock endpoint).
4 - On Microsoft Foundry, Claude Opus 4.8 has a 200k-token context window. See Claude in Microsoft Foundry.
Claude Mythos Preview is offered separately as a research preview model for defensive cybersecurity workflows as part of Project Glasswing. Access is invitation-only and there is no self-serve sign-up.
20250929) are fixed to that specific release. Starting with the Claude 4.6 generation, model IDs use a dateless format that is also a pinned snapshot, not an evergreen pointer. For models before the 4.6 generation, entries in the Claude API alias column are convenience pointers that resolve to a dated model ID. For details on the naming convention and how versioning works, see Model IDs and versioning.claude-opus-4-6), not Bedrock-style IDs. Model lifecycle on Claude Platform on AWS follows Anthropic's first-party Model deprecations, not Bedrock's. See Available models for the model list.You can query model capabilities and token limits programmatically with the Models API. The response includes max_input_tokens, max_tokens, and a capabilities object for every available model.
On Claude Opus 4.8, the effort parameter defaults to high on all surfaces, including the Claude API and Claude Code. Set effort explicitly to use a different level. See Effort for guidance on choosing a level.
The Max output values above apply to the synchronous Messages API. On the Message Batches API, Claude Opus 4.8, Opus 4.7, Opus 4.6, and Sonnet 4.6 support up to 300k output tokens by using the output-300k-2026-03-24 beta header.
Claude 4 models excel in:
Performance: Top-tier results in reasoning, coding, multilingual tasks, long-context handling, honesty, and image processing. See the Claude 4 blog post for more information.
Engaging responses: Claude models are ideal for applications that require rich, human-like interactions.
Output quality: When migrating from previous model generations to Claude 4, you may notice larger improvements in overall performance.
If you're currently using Claude Opus 4.7 or earlier Claude models, see Migrating to Claude Opus 4.8.
If you're currently using Claude Opus 4.6 or older Claude models, see Migrating to Claude Opus 4.7.
If you're ready to start exploring what Claude can do for you, dive in! Whether you're a developer looking to integrate Claude into your applications or a user wanting to experience the power of AI firsthand, the following resources can help.
Explore Claude's capabilities and development flow.
Learn how to make your first API call in minutes.
Craft and test powerful prompts directly in your browser.
If you have any questions or need assistance, don't hesitate to reach out to the support team or consult the Discord community.
Was this page helpful?
| Max output | 128k tokens | 128k tokens | 
| Pricing | $10 / $50 per MTok (input / output) | $10 / $50 per MTok (input / output) | 
| Pricing1 | 
| $5 / input MTok $25 / output MTok | 
| $3 / input MTok $15 / output MTok | 
| $1 / input MTok $5 / output MTok | 
| Extended thinking | No | Yes | Yes | 
| Adaptive thinking | Yes | Yes | No | 
| Priority Tier | Yes | Yes | Yes | 
| Comparative latency | Moderate | Fast | Fastest | 
| Context window | 1M tokens4 | 1M tokens | 200k tokens | 
| Max output | 128k tokens | 128k tokens | 64k tokens | 
| Reliable knowledge cutoff | Jan 20262 | Aug 20252 | Feb 2025 | 
| Training data cutoff | Jan 2026 | Jan 2026 | Jul 2025 |
