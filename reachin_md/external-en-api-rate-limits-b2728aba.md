---
title: https://docs.anthropic.com/en/api/rate-limits#rate-limits
source_url: https://docs.anthropic.com/en/api/rate-limits#rate-limits
notion_source: Anthropic
---

Claude Platform on AWS: The rate limits on this page apply to Claude Platform on AWS, but billing and limit management differ. Billing is through AWS Marketplace (not Anthropic credit purchases). Organizations on Claude Platform on AWS are placed on the Start tier and do not move between usage tiers automatically. To request higher limits, contact your Anthropic account representative or Anthropic support; the Request rate limit increase flow is not available. Spend limits are set in Settings > Billing rather than Settings > Limits. Per-workspace rate limit configuration and fast mode are not available on Claude Platform on AWS. For details, see Rate limits and quotas on Claude Platform on AWS.
There are two types of limits:
The API enforces service-configured limits at the organization level, but you may also set user-configurable limits for your organization's workspaces.
Claude Platform on AWS: Spend limits work differently on Claude Platform on AWS. Set spend limits in Settings > Billing instead of Settings > Limits. See Spend limits on Claude Platform on AWS for how spend caps and self-set spend limits apply to your organization.
Each of the Start, Build, and Scale tiers carries a monthly spend cap, which is the maximum your organization can spend on the API each calendar month. Once you reach your tier's spend cap, API usage pauses until the next month unless you request a higher limit. You can view your organization's monthly spend cap on the Limits page.
| Usage tier | Monthly spend cap | 
|---|---|
| Start | $500 USD | 
| Build | $1,000 USD | 
| Scale | $200,000 USD | 
Organizations on the Custom tier have no monthly spend cap; limits are arranged with their account team.
You can also set your own spend limit below your tier's cap to control costs:
Navigate to the Limits page
Go to Settings > Limits in the Claude Console.
Open the spend limit editor
In the Spend limits section, click Change Limit (or Set spend limit if no limit is currently set).
Adjust your spend limit
Enter a new value. Your spend limit cannot exceed your current tier's cap.
The rate limits for the Messages API are measured in requests per minute (RPM), input tokens per minute (ITPM), and output tokens per minute (OTPM) for each model class.
If you exceed any of the rate limits you will get a 429 error describing which rate limit was exceeded, along with a retry-after header indicating how long to wait.
You might also encounter 429 errors because of acceleration limits on the API if your organization has a sharp increase in usage. To avoid hitting acceleration limits, ramp up your traffic gradually and maintain consistent usage patterns.
Many API providers use a combined "tokens per minute" (TPM) limit that may include all tokens, both cached and uncached, input and output. For most Claude models, only uncached input tokens count toward your ITPM rate limits. This is a key advantage that makes the rate limits effectively higher than they might initially appear.
ITPM rate limits are estimated at the beginning of each request, and the estimate is adjusted during the request to reflect the actual number of input tokens used.
Here's what counts toward ITPM:
input_tokens (tokens after the last cache breakpoint) ✓ Count toward ITPMcache_creation_input_tokens (tokens being written to cache) ✓ Count toward ITPMcache_read_input_tokens (tokens read from cache) ✗ Do NOT count toward ITPM for most modelsThe input_tokens field only represents tokens that appear after your last cache breakpoint, not all input tokens in your request. To calculate total input tokens:
total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokensThis means when you have cached content, input_tokens will typically be much smaller than your total input. For example, with a 200k token cached document and a 50 token user question, you'd see input_tokens: 50 even though the total input is 200,050 tokens.
For rate limit purposes on most models, only input_tokens + cache_creation_input_tokens count toward your ITPM limit, making prompt caching an effective way to increase your effective throughput.
Example: With a 2,000,000 ITPM limit and an 80% cache hit rate, you could effectively process 10,000,000 total input tokens per minute (2M uncached + 8M cached), because cached tokens don't count toward your rate limit.
Claude Haiku 3.5 (marked with † in the following rate limit tables) also counts cache_read_input_tokens toward ITPM rate limits.
For all models without the † marker, cached input tokens do not count toward rate limits and are billed at a reduced rate (10% of base input token price). This means you can achieve significantly higher effective throughput by using prompt caching.
Maximize your rate limits with prompt caching
See prompt caching for guidance on increasing effective throughput by caching repeated content such as:
With effective caching, you can dramatically increase your actual throughput without increasing your rate limits. Monitor your cache hit rate on the Usage page to optimize your caching strategy.
OTPM rate limits are evaluated in real time as output tokens are produced, counting only the actual tokens generated. The max_tokens parameter does not factor into OTPM rate limit calculations, so there is no rate limit downside to setting a higher max_tokens value.
Rate limits are applied separately for each model; therefore you can use different models up to their respective limits simultaneously. You can check your current rate limits and behavior on the Limits page in the Claude Console, or read the configured limits programmatically with the Rate Limits API.
Rate limits are currently shared across all inference_geo values. Requests with inference_geo: "us" and inference_geo: "global" draw from the same rate limit pool.
| Model | Maximum requests per minute (RPM) | Maximum input tokens per minute (ITPM) | Maximum output tokens per minute (OTPM) | 
|---|---|---|---|
| Claude Fable 5 | 1,000 | 500,000 | 100,000 | 
| Claude Opus 4.x* | 1,000 | 2,000,000 | 400,000 | 
| Claude Sonnet 5 | 1,000 | 2,000,000 | 400,000 | 
| Claude Sonnet 4.x** | 1,000 | 2,000,000 | 400,000 | 
| Claude Haiku 4.5 | 1,000 | 2,000,000 | 400,000 | 
| Claude Haiku 3.5 (retired, except on Bedrock and Google Cloud) | 1,000 | 100,000† | 20,000 | 
* - Opus rate limit is a total limit that applies to combined traffic across Claude Opus 4.8, Opus 4.7, Opus 4.6, and Opus 4.5.
** - Sonnet 4.x rate limit is a total limit that applies to combined traffic across Sonnet 4.6 and Sonnet 4.5. Claude Sonnet 5 has a separate rate limit and is not part of this combined bucket.
† - Limit counts cache_read_input_tokens toward ITPM usage.
The Message Batches API has its own set of rate limits which are shared across all models. These include a requests per minute (RPM) limit to all API endpoints and a limit on the number of batch requests that can be in the processing queue at the same time. A "batch request" here refers to part of a Message Batch. You may create a Message Batch containing thousands of batch requests, each of which count toward this limit. A batch request is considered part of the processing queue when it has yet to be successfully processed by the model.
| Maximum requests per minute (RPM) | Maximum batch requests in processing queue | Maximum batch requests per batch | 
|---|---|---|
| 1,000 | 200,000 | 100,000 | 
Claude Managed Agents endpoints are rate-limited per organization. These limits are separate from the Messages API rate limits above.
| Operation | Limit | 
|---|---|
| Create endpoints (for example, agents, sessions, and environments) | 300 requests per minute | 
| Read endpoints (for example, retrieve, list, and stream) | 1,200 requests per minute | 
When using fast mode (research preview) with speed: "fast" on Claude Opus 4.8 or Opus 4.7, dedicated rate limits apply that are separate from standard Opus rate limits. When fast mode rate limits are exceeded, the API returns a 429 error with a retry-after header. Fast mode is not available on Claude Opus 4.6: requests to claude-opus-4-6 with speed: "fast" run at standard speed. See Fast mode.
The response includes anthropic-fast-* headers that indicate your fast mode rate limit status. See Fast mode rate limits for details on these headers.
You can monitor your rate limit usage on the Usage page of the Claude Console.
In addition to providing token and request charts, the Usage page provides two separate rate limit charts. Use these charts to see what headroom you have to grow, identify when you may be hitting peak use, understand what rate limits to request, and learn how to improve your caching rates. The charts visualize a number of metrics for a given rate limit (for example, per model):
To request higher rate limits or a higher monthly spend cap, use Request rate limit increase on the Limits page.
Support can also raise limits. For urgent needs, contact Anthropic support.
Claude Platform on AWS: The Request rate limit increase flow is not available. Contact your Anthropic account representative or Anthropic support, and include the models you need raised, your peak input and output tokens per minute for each model, and roughly what share of your input is cached or repeated context. See Rate limits and quotas on Claude Platform on AWS.
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
Was this page helpful?
