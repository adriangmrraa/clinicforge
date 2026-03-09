# 📊 Google Ads Integration for ClinicForge

## 🎯 Overview

Complete Google Ads integration for ClinicForge, allowing clinics to:
- Connect Google Ads accounts via OAuth 2.0
- Track campaign performance and ROI
- View combined metrics with Meta Ads
- Automatic data synchronization

## 🏗️ Architecture

### Backend Components:
1. **Google OAuth Service** (`services/auth/google_oauth_service.py`)
   - OAuth 2.0 authentication flow
   - Token management and refresh
   - Multi-platform support (ads/login)

2. **Google Ads Service** (`services/marketing/google_ads_service.py`)
   - Google Ads API integration
   - Campaign metrics retrieval
   - Demo data fallback

3. **API Routes**:
   - `/admin/auth/google/` - OAuth endpoints
   - `/admin/marketing/google/` - Ads API endpoints

4. **Database Tables**:
   - `google_oauth_tokens` - OAuth tokens storage
   - `google_ads_accounts` - Customer accounts
   - `google_ads_metrics_cache` - Performance cache

### Frontend Components:
1. **GoogleConnectionWizard** - Step-by-step connection UI
2. **MarketingHubView** - Updated with Google Ads tabs
3. **GoogleAdsApi** - TypeScript API client
4. **Translations** - Spanish and English support

## 🚀 Installation & Setup

### 1. Database Migration
```bash
# Run the Google Ads migration
python3 run_google_migration.py run

# Check migration status
python3 run_google_migration.py status
```

### 2. Google Cloud Console Configuration

#### Step 1: Create or Select Project
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing: `clinicforge-google-ads`
3. Enable billing (required for Google Ads API)

#### Step 2: Enable Required APIs
1. **Google Ads API** - For campaign data access
2. **OAuth 2.0** - For user authentication
3. **People API** (optional) - For user profile info

#### Step 3: Configure OAuth Consent Screen
1. **Application type**: "Web application"
2. **Application name**: "ClinicForge Google Ads"
3. **User support email**: Your support email
4. **Developer contact email**: Your developer email
5. **Scopes to add**:
   - `.../auth/adwords` (Google Ads API)
   - `.../auth/userinfo.email` (User email)
   - `openid` (OpenID Connect)

#### Step 4: Create OAuth Credentials
1. **Create credentials** → "OAuth client ID"
2. **Application type**: "Web application"
3. **Name**: "ClinicForge Web Client"
4. **Authorized redirect URIs**:
   ```
   http://localhost:8000/admin/auth/google/ads/callback
   http://localhost:8000/admin/auth/google/login/callback
   https://your-domain.com/admin/auth/google/ads/callback
   https://your-domain.com/admin/auth/google/login/callback
   ```
5. **Copy Client ID and Client Secret**

#### Step 5: Request Google Ads API Access
1. Go to [Google Ads API Access](https://ads.google.com/aw/apicenter)
2. Fill application form (takes 2-5 business days)
3. Request **Standard Access** (not Test Access)
4. Get **Developer Token**

### 3. Environment Variables

Add to your `.env` file:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/admin/auth/google/ads/callback
GOOGLE_LOGIN_REDIRECT_URI=http://localhost:8000/admin/auth/google/login/callback

# Google Ads API Configuration
GOOGLE_DEVELOPER_TOKEN=your-developer-token
GOOGLE_ADS_API_VERSION=v16

# Frontend URL (for OAuth redirects)
FRONTEND_URL=http://localhost:5173
PLATFORM_URL=http://localhost:8000
```

### 4. Per-Tenant Configuration (Optional)

Tenants can override global credentials in Settings → Credentials:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_DEVELOPER_TOKEN`
- `GOOGLE_REDIRECT_URI`
- `GOOGLE_LOGIN_REDIRECT_URI`

## 🔧 API Endpoints

### OAuth Endpoints (`/admin/auth/google/`)
- `GET /ads/url` - Get OAuth authorization URL
- `GET /ads/callback` - OAuth callback handler
- `GET /login/url` - Google Login URL
- `GET /login/callback` - Google Login callback
- `POST /ads/disconnect` - Disconnect Google Ads
- `GET /ads/refresh` - Refresh access token
- `GET /ads/test-connection` - Test API connection

### Google Ads Endpoints (`/admin/marketing/google/`)
- `GET /campaigns` - Get campaigns with metrics
- `GET /metrics` - Get aggregated metrics
- `GET /customers` - Get accessible customer accounts
- `POST /sync` - Trigger manual data sync
- `GET /stats` - Comprehensive stats (campaigns + metrics)
- `GET /connection-status` - Get connection status
- `GET /combined-stats` - Combined Meta + Google stats
- `GET /debug/config` - Debug configuration

### Combined Marketing Endpoints (`/admin/marketing/`)
- `GET /combined-stats` - Combined platform stats
- `GET /multi-platform-campaigns` - Campaigns from all platforms
- `GET /platform-status` - Connection status for all platforms

## 🎨 Frontend Features

### 1. Marketing Hub Tabs
- **Meta Ads** - Existing Meta Ads functionality
- **Google Ads** - New Google Ads dashboard
- **Combined** - Unified view of both platforms

### 2. Google Connection Wizard
- Step 1: Welcome & benefits
- Step 2: Manual configuration (if needed)
- Step 3: OAuth authorization
- Step 4: Connection complete

### 3. Google Ads Dashboard
- Campaign performance metrics
- Real-time data synchronization
- Demo data fallback
- Currency formatting (micros → currency)

### 4. Combined Analytics
- Total impressions, clicks, cost
- Platform distribution
- ROI comparison
- Performance trends

## 🧪 Testing

### 1. Local Development Testing
```bash
# Test without Google credentials (demo mode)
# 1. Start the backend
cd orchestrator_service && python3 main.py

# 2. Start the frontend
cd frontend_react && npm run dev

# 3. Navigate to Marketing Hub
# 4. Switch to Google Ads tab
# 5. View demo data
```

### 2. OAuth Flow Testing
```bash
# Test with sandbox credentials
# 1. Use Google Ads API test account
# 2. Set GOOGLE_DEVELOPER_TOKEN to test token
# 3. Test complete OAuth flow
```

### 3. Production Testing
```bash
# 1. Deploy with real credentials
# 2. Test with actual Google Ads account
# 3. Verify data synchronization
# 4. Test error handling
```

## ⚠️ Common Issues & Troubleshooting

### 1. OAuth Redirect URI Mismatch
**Error**: `redirect_uri_mismatch`
**Solution**: Ensure redirect URIs in Google Cloud Console match exactly (including http/https, ports, paths)

### 2. Developer Token Not Approved
**Error**: `DEVELOPER_TOKEN_NOT_APPROVED`
**Solution**: Wait 2-5 business days for approval, or use test token during development

### 3. Insufficient Permissions
**Error**: `PERMISSION_DENIED`
**Solution**: Ensure Google account has access to Google Ads account, and OAuth scopes are correct

### 4. API Quota Exceeded
**Error**: `RESOURCE_EXHAUSTED`
**Solution**: Implement caching, reduce API call frequency, request quota increase

### 5. Token Expired
**Error**: `INVALID_CREDENTIALS`
**Solution**: Automatic token refresh implemented, manual refresh available via API

## 🔒 Security Considerations

### 1. Token Storage
- OAuth tokens encrypted with Fernet
- Stored per-tenant in database
- Automatic refresh before expiration
- Secure deletion on disconnect

### 2. API Security
- All endpoints require CEO authentication
- Multi-tenant data isolation
- Rate limiting implemented
- Input validation and sanitization

### 3. Data Privacy
- Only aggregate metrics stored
- No PII in cache tables
- GDPR-compliant data handling
- Right to erasure implemented

## 📈 Monitoring & Maintenance

### 1. Health Checks
```bash
# Check Google Ads connection status
GET /admin/marketing/google/connection-status

# Check configuration
GET /admin/marketing/google/debug/config

# Check platform status
GET /admin/marketing/platform-status
```

### 2. Logging
- OAuth flow logging
- API request/response logging
- Error logging with context
- Performance metrics logging

### 3. Maintenance Tasks
- Daily token refresh checks
- Weekly cache cleanup
- Monthly quota monitoring
- Quarterly security audit

## 🚀 Deployment Checklist

### Pre-Deployment
- [ ] Google Cloud project created
- [ ] Required APIs enabled
- [ ] OAuth consent screen configured
- [ ] OAuth credentials created
- [ ] Developer token approved
- [ ] Environment variables set
- [ ] Database migration tested
- [ ] Frontend compilation tested

### Deployment
- [ ] Run database migration
- [ ] Deploy backend with new environment variables
- [ ] Deploy frontend with updated build
- [ ] Verify OAuth redirect URIs in production
- [ ] Test connection with real credentials
- [ ] Verify data synchronization

### Post-Deployment
- [ ] Monitor error logs
- [ ] Test all API endpoints
- [ ] Verify frontend functionality
- [ ] Train users on new features
- [ ] Update documentation

## 📚 References

### Official Documentation
- [Google Ads API Documentation](https://developers.google.com/google-ads/api/docs/start)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com)

### ClinicForge Documentation
- [Marketing Hub Overview](../docs/marketing_hub.md)
- [API Reference](../docs/api_reference.md)
- [Database Schema](../docs/database_schema.md)

### Support
- For technical issues: Open GitHub issue
- For configuration help: Contact system administrator
- For Google API issues: Google Ads API support

---

**Last Updated**: March 3, 2026  
**Version**: 1.0.0  
**Status**: Production Ready 🚀