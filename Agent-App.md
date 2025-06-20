# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**LoanX.ai Agent App** is an AI-powered real estate document analysis platform that combines modern web technologies with advanced AI capabilities to streamline property analysis and loan processing workflows.

## Technology Stack

- **Frontend**: Remix (React) with TypeScript, TailwindCSS, Shadcn/UI components
- **Backend**: Firebase (Firestore, Cloud Storage, Cloud Functions)
- **AI Engine**: Anthropic Claude Opus 4 with LangChain/LangGraph SDK
- **Authentication**: Clerk
- **Build System**: Vite
- **Styling**: TailwindCSS with custom design system

## Development Commands

```bash
# Development
npm run dev              # Start development server
npm run dev:local        # Start development with local environment
npm run build           # Production build
npm run start           # Start production server

# Code Quality
npm run lint            # ESLint checking
npm run typecheck       # TypeScript type checking

# Firebase
npm run deploy          # Deploy to Firebase (functions)
```

## Architecture Overview

### Core Structure
- `/app` - Remix application routes and components
- `/functions` - Firebase Cloud Functions for document processing
- `/lib` - Shared utilities, Firebase config, AI agent logic
- `/components` - Reusable UI components (Shadcn/UI based)

### Key Architecture Patterns

**1. AI Agent System (`/lib/ai/`)**
- Advanced Claude Opus 4 integration with 8000-token thinking budget
- Tool orchestration with rate calculations, search, and profile management
- Streaming responses with real-time progress tracking
- Multi-step workflows with context preservation

**2. Firebase Integration**
- Document storage and processing in Cloud Storage
- Firestore for project/property data and chat history
- Cloud Functions for OCR, categorization, and file processing
- Real-time subscriptions for live updates

**3. Authentication & Authorization**
- Clerk for user management and authentication
- Firebase security rules for data access control
- Role-based permissions for project sharing

**4. Document Processing Pipeline**
- OCR extraction from uploaded documents
- AI-powered categorization and analysis
- Structured data extraction for loan documents
- File organization and metadata management

## Development Setup

1. **Environment Variables** (`.env.local`):
   ```
   ANTHROPIC_API_KEY=          # Claude Opus 4 access
   NEXT_PUBLIC_CLERK_*=        # Clerk authentication
   FIREBASE_*=                 # Firebase project config
   REPLICATE_API_TOKEN=        # For document processing
   ```

2. **Firebase Setup**:
   - Initialize Firebase project
   - Enable Firestore, Storage, and Functions
   - Deploy security rules from `/firestore.rules`
   - Configure Cloud Functions

3. **Clerk Configuration**:
   - Set up Clerk application
   - Configure authentication providers
   - Set up webhooks for user management

## Key Components

### AI Agent (`/lib/ai/agent.ts`)
- Claude Opus 4 with extended thinking capabilities
- Tool system for calculations and data retrieval
- Streaming response handling with progress updates
- Context management for multi-turn conversations

### Document Management (`/app/routes/projects/`)
- File upload and processing workflows
- Document categorization and analysis
- Real-time progress tracking
- Collaborative document sharing

### Rate Calculator (`/lib/ai/tools/rate-calculation.ts`)
- Mortgage rate calculations
- APR computations
- Payment schedule generation
- Regulatory compliance checks

## Mobile-First Design

The application uses a Claude-style collapsible interface:
- Responsive sidebar navigation
- Mobile-optimized chat interface
- Touch-friendly document interaction
- Progressive web app capabilities

## Firebase Cloud Functions

Located in `/functions/src/`:
- **Document Processing**: OCR, categorization, metadata extraction
- **User Management**: Clerk webhook handlers
- **Rate Calculations**: Complex financial computations
- **File Operations**: Upload, conversion, organization

## Testing & Quality

- TypeScript strict mode enabled
- ESLint with Remix and React rules
- Tailwind CSS for consistent styling
- Component testing with React Testing Library (when present)

## Common Patterns

### AI Integration
```typescript
// Streaming AI responses
const response = await ai.stream(messages, {
  tools: [rateCalculationTool, searchTool],
  maxTokens: 8000
});
```

### Firebase Operations
```typescript
// Document operations
const docRef = await addDoc(collection(db, 'projects'), data);
const snapshot = await getDocs(query(collection(db, 'documents')));
```

### Route Structure
- `/projects` - Main application workspace
- `/chat` - AI conversation interface
- `/documents` - Document management
- `/calculator` - Standalone rate calculator

## Deployment

1. **Frontend**: Deployed via Remix build to Firebase Hosting
2. **Functions**: Firebase Cloud Functions for backend processing
3. **Database**: Firestore with security rules
4. **Storage**: Cloud Storage for document files

## Troubleshooting

### Common Issues
- **Claude API Limits**: Monitor token usage and implement rate limiting
- **Firebase Quota**: Check Firestore read/write limits
- **Upload Issues**: Verify Cloud Storage CORS configuration
- **Authentication**: Ensure Clerk webhook endpoints are accessible

### Development Tips
- Use `npm run dev:local` for local Firebase emulation
- Monitor Firebase console for function logs
- Check Clerk dashboard for authentication issues
- Use browser DevTools for client-side debugging