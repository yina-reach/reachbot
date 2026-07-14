---
title: https://docs.anthropic.com/en/api/rate-limits
source_url: https://docs.anthropic.com/en/api/rate-limits
notion_source: Anthropic
---

Claude Platform on AWS: The rate limits on this page apply. Billing and spend limits differ: spend limits are not available, and billing is through AWS Marketplace (not Anthropic credit purchases). Organizations start at Tier 1. Rate limit increases go through your Anthropic account representative; there is no automatic tier advancement, and per-workspace rate limit configuration is not available. Fast mode is not available on Claude Platform on AWS.
There are two types of limits:
The API enforces service-configured limits at the organization level, but you may also set user-configurable limits for your organization's workspaces.
These limits apply to both Standard and Priority Tier usage. For more information about Priority Tier, which offers enhanced service levels in exchange for committed spend, see Service Tiers.
Was this page helpful?
Each usage tier has a limit on how much you can spend on the API each calendar month. Once you reach the spend limit of your tier, until you qualify for the next tier, you will have to wait until the next month to be able to use the API again.
To qualify for the next tier, you must meet a deposit requirement. To minimize the risk of overfunding your account, you cannot deposit more than your monthly spend limit.
| Usage tier | Credit purchase | Max credit purchase | Monthly spend limit | 
|---|---|---|---|
| Tier 1 | $5 | $500 | $500 | 
| Tier 2 | $40 | $500 | $500 | 
| Tier 3 | $200 | $1,000 | $1,000 | 
| Tier 4 | $400 | $200,000 | $200,000 | 
| Monthly Invoicing | N/A | N/A | No limit | 
Credit purchase shows the cumulative credit purchases (excluding tax) required to advance to that tier. You advance immediately upon reaching the threshold.
Max credit purchase limits the maximum amount you can add to your account in a single transaction to prevent account overfunding.
Monthly spend limit is the maximum you can spend on the API each calendar month at that tier.
Your organization has two kinds of spend limits: a customer-set limit you control directly, and a tier-enforced ceiling set by your usage tier. Each has a different process for increasing it.
You can set a spend limit lower than your tier's ceiling to control costs. To adjust it:
Navigate to the Limits page
Go to Settings > Limits in the Claude Console.
Open the spend limit editor
In the Spend limits section, click Change Limit (or Set spend limit if no limit is currently set).
Adjust your spend limit
Enter a new value. Your customer-set limit cannot exceed your current tier's limit.
When you need a limit higher than your tier's ceiling (Tier 4's ceiling is $200,000 per month), click Contact Sales on the Limits page. This opens the contact form in a new tab, and a member of the sales team will follow up by email when your organization is upgraded.
Monthly Invoicing removes the monthly spend cap entirely and uses Net-30 payment terms by default.
Support can also raise tier-enforced limits. For urgent needs, contact support.
The rate limits for the Messages API are measured in requests per minute (RPM), input tokens per minute (ITPM), and output tokens per minute (OTPM) for each model class.
If you exceed any of the rate limits you will get a 429 error describing which rate limit was exceeded, along with a retry-after header indicating how long to wait.
You might also encounter 429 errors because of acceleration limits on the API if your organization has a sharp increase in usage. To avoid hitting acceleration limits, ramp up your traffic gradually and maintain consistent usage patterns.
Many API providers use a combined "tokens per minute" (TPM) limit that may include all tokens, both cached and uncached, input and output. For most Claude models, only uncached input tokens count towards your ITPM rate limits. This is a key advantage that makes the rate limits effectively higher than they might initially appear.
ITPM rate limits are estimated at the beginning of each request, and the estimate is adjusted during the request to reflect the actual number of input tokens used.
Here's what counts towards ITPM:
input_tokens (tokens after the last cache breakpoint) ✓ Count towards ITPMcache_creation_input_tokens (tokens being written to cache) ✓ Count towards ITPMcache_read_input_tokens (tokens read from cache) ✗ Do NOT count towards ITPM for most modelsThe input_tokens field only represents tokens that appear after your last cache breakpoint, not all input tokens in your request. To calculate total input tokens:
total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokensThis means when you have cached content, input_tokens will typically be much smaller than your total input. For example, with a 200k token cached document and a 50 token user question, you'd see input_tokens: 50 even though the total input is 200,050 tokens.
For rate limit purposes on most models, only input_tokens + cache_creation_input_tokens count toward your ITPM limit, making prompt caching an effective way to increase your effective throughput.
Example: With a 2,000,000 ITPM limit and an 80% cache hit rate, you could effectively process 10,000,000 total input tokens per minute (2M uncached + 8M cached), because cached tokens don't count towards your rate limit.
Claude Haiku 3.5 (marked with † in the following rate limit tables) also counts cache_read_input_tokens toward ITPM rate limits.
For all models without the † marker, cached input tokens do not count towards rate limits and are billed at a reduced rate (10% of base input token price). This means you can achieve significantly higher effective throughput by using prompt caching.
Maximize your rate limits with prompt caching
To get the most out of your rate limits, use prompt caching for repeated content like:
With effective caching, you can dramatically increase your actual throughput without increasing your rate limits. Monitor your cache hit rate on the Usage page to optimize your caching strategy.
OTPM rate limits are evaluated in real time as output tokens are produced, counting only the actual tokens generated. The max_tokens parameter does not factor into OTPM rate limit calculations, so there is no rate limit downside to setting a higher max_tokens value.
Rate limits are applied separately for each model; therefore you can use different models up to their respective limits simultaneously. You can check your current rate limits and behavior in the Claude Console, or read the configured limits programmatically with the Rate Limits API.
Rate limits are currently shared across all inference_geo values. Requests with inference_geo: "us" and inference_geo: "global" draw from the same rate limit pool.
* - Opus rate limit is a total limit that applies to combined traffic across Claude Opus 4.8, Opus 4.7, Opus 4.6, Opus 4.5, and Opus 4.1 (deprecated).
** - Sonnet 4.x rate limit is a total limit that applies to combined traffic across Sonnet 4.6 and Sonnet 4.5.
† - Limit counts cache_read_input_tokens towards ITPM usage.
The Message Batches API has its own set of rate limits which are shared across all models. These include a requests per minute (RPM) limit to all API endpoints and a limit on the number of batch requests that can be in the processing queue at the same time. A "batch request" here refers to part of a Message Batch. You may create a Message Batch containing thousands of batch requests, each of which count towards this limit. A batch request is considered part of the processing queue when it has yet to be successfully processed by the model.
Claude Managed Agents endpoints are rate-limited per organization. These limits are separate from the Messages API rate limits above.
| Operation | Limit | 
|---|---|
| Create endpoints (for example, agents, sessions, and environments) | 300 requests per minute | 
| Read endpoints (for example, retrieve, list, and stream) | 600 requests per minute | 
When using fast mode (research preview) with speed: "fast" on Claude Opus 4.8, Opus 4.7, or Opus 4.6, dedicated rate limits apply that are separate from standard Opus rate limits. When fast mode rate limits are exceeded, the API returns a 429 error with a retry-after header.
The response includes anthropic-fast-* headers that indicate your fast mode rate limit status. See Fast mode for details on these headers.
You can monitor your rate limit usage on the Usage page of the Claude Console.
In addition to providing token and request charts, the Usage page provides two separate rate limit charts. Use these charts to see what headroom you have to grow, when you may be hitting peak use, better understand what rate limits to request, or how you can improve your caching rates. The charts visualize a number of metrics for a given rate limit (for example, per model):
For more about workspaces, see Workspaces.
To protect Workspaces in your Organization from potential overuse, you can set custom spend and rate limits per Workspace.
Example: If your Organization's limit is 40,000 input tokens per minute and 8,000 output tokens per minute, you might limit one Workspace to 30,000 input tokens per minute. This protects other Workspaces from potential overuse and ensures a more equitable distribution of resources across your Organization. The remaining unused tokens per minute (or more, if that Workspace doesn't use the limit) are then available for other Workspaces to use.
Note:
To read your current organization and workspace rate limits programmatically, use the Rate Limits API.
The API response includes headers that show you the rate limit enforced, current usage, and when the limit will be reset.
The following headers are returned:
| Header | Description | 
|---|---|
| retry-after | The number of seconds to wait until you can retry the request. Earlier retries will fail. | 
| anthropic-ratelimit-requests-limit | The maximum number of requests allowed within any rate limit period. | 
| anthropic-ratelimit-requests-remaining | The number of requests remaining before being rate limited. | 
| anthropic-ratelimit-requests-reset | The time when the request rate limit will be fully replenished, provided in RFC 3339 format. | 
| anthropic-ratelimit-tokens-limit | The maximum number of tokens allowed within any rate limit period. | 
| anthropic-ratelimit-tokens-remaining | The number of tokens remaining (rounded to the nearest thousand) before being rate limited. | 
| anthropic-ratelimit-tokens-reset | The time when the token rate limit will be fully replenished, provided in RFC 3339 format. | 
| anthropic-ratelimit-input-tokens-limit | The maximum number of input tokens allowed within any rate limit period. | 
| anthropic-ratelimit-input-tokens-remaining | The number of input tokens remaining (rounded to the nearest thousand) before being rate limited. | 
| anthropic-ratelimit-input-tokens-reset | The time when the input token rate limit will be fully replenished, provided in RFC 3339 format. | 
| anthropic-ratelimit-output-tokens-limit | The maximum number of output tokens allowed within any rate limit period. | 
| anthropic-ratelimit-output-tokens-remaining | The number of output tokens remaining (rounded to the nearest thousand) before being rate limited. | 
| anthropic-ratelimit-output-tokens-reset | The time when the output token rate limit will be fully replenished, provided in RFC 3339 format. | 
| anthropic-priority-input-tokens-limit | The maximum number of Priority Tier input tokens allowed within any rate limit period. (Priority Tier only) | 
| anthropic-priority-input-tokens-remaining | The number of Priority Tier input tokens remaining (rounded to the nearest thousand) before being rate limited. (Priority Tier only) | 
| anthropic-priority-input-tokens-reset | The time when the Priority Tier input token rate limit will be fully replenished, provided in RFC 3339 format. (Priority Tier only) | 
| anthropic-priority-output-tokens-limit | The maximum number of Priority Tier output tokens allowed within any rate limit period. (Priority Tier only) | 
| anthropic-priority-output-tokens-remaining | The number of Priority Tier output tokens remaining (rounded to the nearest thousand) before being rate limited. (Priority Tier only) | 
| anthropic-priority-output-tokens-reset | The time when the Priority Tier output token rate limit will be fully replenished, provided in RFC 3339 format. (Priority Tier only) | 
The anthropic-ratelimit-tokens-* headers display the values for the most restrictive limit currently in effect. For instance, if you have exceeded the Workspace per-minute token limit, the headers will contain the Workspace per-minute token rate limit values. If Workspace limits do not apply, the headers will return the total tokens remaining, where total is the sum of input and output tokens. This approach ensures that you have visibility into the most relevant constraint on your current API usage.
