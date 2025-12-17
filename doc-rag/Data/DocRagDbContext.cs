using Microsoft.EntityFrameworkCore;
using DocRag.Models;

namespace DocRag.Data;

/// <summary>
/// Entity Framework Core database context for DocRAG.
/// </summary>
public class DocRagDbContext : DbContext
{
    public DocRagDbContext(DbContextOptions<DocRagDbContext> options) : base(options)
    {
    }

    public DbSet<Document> Documents { get; set; } = null!;
    public DbSet<Chunk> Chunks { get; set; } = null!;

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Document configuration
        modelBuilder.Entity<Document>(entity =>
        {
            entity.ToTable("documents");
            
            entity.HasKey(e => e.Id);
            
            entity.HasIndex(e => e.DocumentId)
                .IsUnique()
                .HasDatabaseName("idx_documents_document_id");
            
            entity.HasIndex(e => e.ClientId)
                .HasDatabaseName("idx_documents_client_id");

            entity.Property(e => e.CreatedAt)
                .HasDefaultValueSql("NOW()");
        });

        // Chunk configuration
        modelBuilder.Entity<Chunk>(entity =>
        {
            entity.ToTable("chunks");
            
            entity.HasKey(e => e.Id);
            
            entity.HasIndex(e => e.ChunkId)
                .IsUnique()
                .HasDatabaseName("idx_chunks_chunk_id");
            
            entity.HasIndex(e => e.DocumentId)
                .HasDatabaseName("idx_chunks_doc");
            
            entity.HasIndex(e => e.ClientId)
                .HasDatabaseName("idx_chunks_client");
            
            entity.HasIndex(e => e.ChunkType)
                .HasDatabaseName("idx_chunks_type");

            entity.Property(e => e.CreatedAt)
                .HasDefaultValueSql("NOW()");
            
            entity.Property(e => e.ChunkType)
                .HasDefaultValue("general");
        });
    }
}
