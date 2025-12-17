using Microsoft.AspNetCore.Mvc;
using DocRag.Models.Dto;
using DocRag.Services;

namespace DocRag.Controllers;

/// <summary>
/// API controller for document search and RAG question answering.
/// </summary>
[ApiController]
[Route("api")]
public class DocRagController : ControllerBase
{
    private readonly ISearchService _searchService;
    private readonly IQaService _qaService;
    private readonly ILogger<DocRagController> _logger;

    public DocRagController(
        ISearchService searchService,
        IQaService qaService,
        ILogger<DocRagController> logger)
    {
        _searchService = searchService;
        _qaService = qaService;
        _logger = logger;
    }

    /// <summary>
    /// Fulltext search in documents.
    /// </summary>
    /// <param name="request">Search request with query and optional filters.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Search results with snippets and ranking.</returns>
    [HttpPost("search")]
    [ProducesResponseType(typeof(SearchResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<SearchResponse>> Search(
        [FromBody] SearchRequest request,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
        {
            return BadRequest(new { error = "Query is required" });
        }

        if (request.Query.Length < 3)
        {
            return BadRequest(new { error = "Query must be at least 3 characters" });
        }

        _logger.LogInformation("Search request: {Query}", request.Query);

        var result = await _searchService.SearchDocumentsAsync(request, ct);
        return Ok(result);
    }

    /// <summary>
    /// RAG-based question answering.
    /// </summary>
    /// <param name="request">Query request with question and optional filters.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Answer with confidence score and sources.</returns>
    [HttpPost("query")]
    [ProducesResponseType(typeof(QueryResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<QueryResponse>> Query(
        [FromBody] QueryRequest request,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
        {
            return BadRequest(new { error = "Query is required" });
        }

        try
        {
            _logger.LogInformation("Query request: {Query}", request.Query);
            
            var result = await _qaService.AnswerQuestionAsync(request, ct);
            return Ok(result);
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Health check endpoint.
    /// </summary>
    [HttpGet("health")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public IActionResult Health()
    {
        return Ok(new { status = "healthy", timestamp = DateTime.UtcNow });
    }
}
