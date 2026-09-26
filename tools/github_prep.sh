#!/bin/bash
# Huxley GitHub Prep - Reduces 7.8GB to ~100MB for backup

echo "🧹 Huxley GitHub Prep Starting..."
echo "Current size: $(du -sh . | cut -f1)"

# 1. Remove all node_modules (the biggest culprit)
echo "Removing node_modules directories..."
find . -name "node_modules" -type d -prune -exec rm -rf {} + 2>/dev/null

# 2. Clean Python cache
echo "Cleaning Python cache..."
find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 3. Clean Next.js builds
echo "Cleaning Next.js builds..."
find . -name ".next" -type d -prune -exec rm -rf {} + 2>/dev/null

# 4. Remove logs
echo "Cleaning logs..."
find . -name "*.log" -type f -delete 2>/dev/null

# 5. Check for remaining .env files
echo ""
echo "⚠️  Found .env files (won't be pushed if gitignore is correct):"
find . -name "*.env*" -type f ! -name "*.example" 2>/dev/null | head -10

echo ""
echo "✅ Cleanup complete!"
echo "New size: $(du -sh . | cut -f1)"
echo ""
echo "Next steps:"
echo "1. Replace current .gitignore: cp .gitignore-simple .gitignore"
echo "2. Review .env files above"
echo "3. git add ."
echo "4. git commit -m 'Huxley framework backup'"
echo "5. git push"
echo ""
echo "📦 What gets backed up:"
echo "✅ Huxley framework & tools"
echo "✅ Templates & documentation" 
echo "✅ Global configs & agents"
echo "❌ Individual capsules (upload separately if needed)"