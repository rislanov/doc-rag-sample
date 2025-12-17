using Microsoft.EntityFrameworkCore;
using DocRag.Data;
using DocRag.Services;

var builder = WebApplication.CreateBuilder(args);

// Add environment-specific configuration
if (builder.Environment.IsProduction() || Environment.GetEnvironmentVariable("DOTNET_RUNNING_IN_CONTAINER") == "true")
{
    builder.Configuration.AddJsonFile("appsettings.Docker.json", optional: true, reloadOnChange: false);
}

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new() 
    { 
        Title = "DocRAG API", 
        Version = "v1",
        Description = "Document RAG API with fulltext search and LLM-based Q&A"
    });
});

// Configure Entity Framework with PostgreSQL + pgvector
builder.Services.AddDbContext<DocRagDbContext>(options =>
{
    options.UseNpgsql(
        builder.Configuration.GetConnectionString("DefaultConnection"),
        npgsqlOptions =>
        {
            npgsqlOptions.EnableRetryOnFailure(maxRetryCount: 5);
            npgsqlOptions.UseVector();  // Enable pgvector support
        });
});

// Configure HTTP client for Ollama LLM
builder.Services.AddHttpClient<IOllamaService, OllamaService>(client =>
{
    var baseUrl = builder.Configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = TimeSpan.FromMinutes(2); // LLM generation can take time
});

// Configure HTTP client for Ollama Embeddings
builder.Services.AddHttpClient<IEmbeddingService, OllamaEmbeddingService>(client =>
{
    var baseUrl = builder.Configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = TimeSpan.FromSeconds(30);
});

// Register services
builder.Services.AddScoped<ISearchService, SearchService>();
builder.Services.AddScoped<IQaService, QaService>();

// Configure CORS
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
            .AllowAnyMethod()
            .AllowAnyHeader();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors();
app.MapControllers();

// Apply migrations on startup (optional, can be disabled in production)
using (var scope = app.Services.CreateScope())
{
    var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();
    var context = scope.ServiceProvider.GetRequiredService<DocRagDbContext>();
    
    try
    {
        logger.LogInformation("Checking database connection...");
        await context.Database.CanConnectAsync();
        logger.LogInformation("Database connection successful");
    }
    catch (Exception ex)
    {
        logger.LogWarning(ex, "Database not available, migrations may need to be applied manually");
    }
}

app.Run();
