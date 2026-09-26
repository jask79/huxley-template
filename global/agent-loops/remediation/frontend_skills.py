"""
Frontend-specific remediation skills for React/Next.js development.

10 remediation patterns for common frontend errors.
"""

import time

from .skill import RemediationSkill, SkillMetadata, SkillType
from .skill_library import SkillLibrary


def seed_frontend_skills(library: SkillLibrary) -> None:
    """Seed 10 frontend-specific remediation skills."""

    skills = [
        # 1. Fix React Hook Dependency
        RemediationSkill(
            skill_id="fix_react_hook_dependency",
            name="Fix React Hook Dependency Warning",
            description="Add missing dependencies to useEffect/useCallback dependency array",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"React Hook .* has a missing dependency",
                r"missing dependency.*useEffect",
                r"missing dependency.*useCallback",
                r"missing dependency.*useMemo",
            ],
            applicable_categories=["build_error", "test_failure", "runtime_error"],
            fix_template="""
At line {line_number} in {file_path}, add missing dependencies to hook:

useEffect(() => {{
  // your effect code
}}, [missingDependency1, missingDependency2])  // Add these

If the dependency causes infinite loops:
- Wrap it in useCallback/useMemo
- Use ref if it's for side effects only
- Split the effect into multiple effects

If ESLint suggests exhaustive-deps, add the dependency or disable with:
// eslint-disable-next-line react-hooks/exhaustive-deps
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "hooks", "useEffect", "dependencies"],
        ),
        # 2. Fix JSX Syntax
        RemediationSkill(
            skill_id="fix_jsx_syntax",
            name="Fix JSX Syntax Error",
            description="Correct JSX syntax issues (self-closing tags, className, fragments)",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Expected corresponding JSX closing tag",
                r"Adjacent JSX elements must be wrapped",
                r"class.*is not a valid.*use className",
                r"for.*is not a valid.*use htmlFor",
            ],
            applicable_categories=["syntax_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix JSX syntax:

1. Close self-closing tags:
   <img src="..." />  ✅
   <img src="...">    ❌

2. Wrap multiple elements:
   <>
     <div>Element 1</div>
     <div>Element 2</div>
   </>

3. Use className, not class:
   <div className="container">  ✅
   <div class="container">      ❌

4. Use htmlFor, not for:
   <label htmlFor="input">  ✅
   <label for="input">      ❌

5. Properly close all tags:
   <Component></Component>  or  <Component />
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "jsx", "syntax"],
        ),
        # 3. Fix Import Path
        RemediationSkill(
            skill_id="fix_import_path",
            name="Fix Module Import Path",
            description="Resolve incorrect import paths and module resolution errors",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Cannot find module",
                r"Module not found",
                r"Unable to resolve path",
                r"TS2307.*Cannot find module",
            ],
            applicable_categories=["build_error", "missing_dependency", "type_error"],
            fix_template="""
At line {line_number} in {file_path}, fix import path:

1. Check file extension:
   import Button from './Button'      // ✅ (no .tsx/.ts needed)
   import Button from './Button.tsx'  // ❌ (usually)

2. Use path alias if configured:
   import Button from '@/components/Button'  // ✅
   import Button from '../../../components/Button'  // ❌ (too many ..)

3. For npm packages, ensure installed:
   npm install {missing_module}
   pnpm add {missing_module}

4. Check case sensitivity:
   import Button from './button'  // ❌ on some systems
   import Button from './Button'  // ✅

5. For types, install @types package:
   npm install --save-dev @types/{package_name}
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["imports", "modules", "typescript", "react"],
        ),
        # 4. Fix Prop Types
        RemediationSkill(
            skill_id="fix_prop_types",
            name="Fix Component Prop Types",
            description="Add or correct TypeScript prop type definitions",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"TS2322.*Type .* is not assignable to type",
                r"Property .* does not exist on type",
                r"TS2339.*Property .* does not exist",
                r"Missing required prop",
            ],
            applicable_categories=["type_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix prop types:

1. Define interface for props:
   interface ButtonProps {{
     variant?: 'primary' | 'secondary'
     children: React.ReactNode
     onClick?: () => void
   }}

   export const Button: React.FC<ButtonProps> = ({{ variant, children, onClick }}) => {{}}

2. For optional props, add ?:
   name?: string  // Optional
   name: string   // Required

3. Use correct React types:
   children: React.ReactNode
   onClick: React.MouseEventHandler<HTMLButtonElement>
   onChange: React.ChangeEventHandler<HTMLInputElement>
   style: React.CSSProperties

4. Extend HTML element props:
   interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {{
     variant?: 'primary' | 'secondary'
   }}
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["typescript", "react", "props", "types"],
        ),
        # 5. Fix State Mutation
        RemediationSkill(
            skill_id="fix_state_mutation",
            name="Fix Direct State Mutation",
            description="Replace direct mutations with immutable updates",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Do not mutate.*directly",
                r"Cannot assign to.*because it is a constant",
                r"state.*should not be mutated",
            ],
            applicable_categories=["runtime_error", "test_failure"],
            fix_template="""
At line {line_number} in {file_path}, fix state mutation:

1. For arrays, use spread or methods:
   ❌ state.push(item)
   ✅ setState([...state, item])

   ❌ state[0] = newValue
   ✅ setState(state.map((val, i) => i === 0 ? newValue : val))

2. For objects, use spread:
   ❌ state.property = value
   ✅ setState({{ ...state, property: value }})

3. For nested objects:
   ✅ setState({{
     ...state,
     nested: {{ ...state.nested, property: value }}
   }})

4. Use functional update for complex logic:
   setState(prev => ({{
     ...prev,
     count: prev.count + 1
   }}))

5. Consider using useReducer for complex state:
   const [state, dispatch] = useReducer(reducer, initialState)
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "state", "immutability"],
        ),
        # 6. Add Key Prop
        RemediationSkill(
            skill_id="add_key_prop",
            name="Add Missing Key Prop to List Items",
            description="Add unique key prop to list items in React",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Each child in a list should have a unique.*key",
                r"Warning: Each child in an array",
                r"missing.*key.*prop",
            ],
            applicable_categories=["runtime_error", "test_failure"],
            fix_template="""
At line {line_number} in {file_path}, add key prop:

1. Use unique ID if available:
   items.map(item => (
     <Card key={{item.id}}>{{item.name}}</Card>
   ))

2. Use index as last resort (not recommended for dynamic lists):
   items.map((item, index) => (
     <Card key={{index}}>{{item.name}}</Card>
   ))

3. For static lists, index is fine:
   ['red', 'blue', 'green'].map((color, i) => (
     <div key={{i}}>{{color}}</div>
   ))

4. For fragments:
   items.map(item => (
     <Fragment key={{item.id}}>
       <div>{{item.name}}</div>
     </Fragment>
   ))

⚠️ Never use random values (Math.random()) as keys!
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "keys", "lists"],
        ),
        # 7. Fix Event Handler
        RemediationSkill(
            skill_id="fix_event_handler",
            name="Fix Event Handler Signature",
            description="Correct event handler types and signatures",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"TS2322.*Type '.*' is not assignable to type '.*EventHandler",
                r"Property .* does not exist on type 'Event'",
                r"Argument of type .* is not assignable to parameter of type.*Event",
            ],
            applicable_categories=["type_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix event handler:

1. Use correct event type:
   const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {{}}
   const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {{}}
   const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {{}}
   const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {{}}

2. Prevent default if needed:
   const handleSubmit = (e: React.FormEvent) => {{
     e.preventDefault()
     // ...
   }}

3. Access event properties:
   const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {{
     const value = e.target.value  // ✅
     const value = e.value          // ❌
   }}

4. For custom handlers without event:
   const handleClick = () => {{}}  // No event parameter

5. Use generic handler type:
   type Handler = (e: React.MouseEvent) => void
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "events", "typescript", "handlers"],
        ),
        # 8. Fix CSS Module Import
        RemediationSkill(
            skill_id="fix_css_module_import",
            name="Fix CSS Module Import and Usage",
            description="Correct CSS module imports and class name references",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Cannot find module.*\.module\.css",
                r"Property .* does not exist.*CSS module",
                r"TS2307.*Cannot find module.*\.css",
            ],
            applicable_categories=["build_error", "type_error"],
            fix_template="""
At line {line_number} in {file_path}, fix CSS module:

1. Import CSS module correctly:
   import styles from './Button.module.css'  // ✅
   import './Button.css'                     // ❌ (global, not module)

2. Use classes from module:
   <div className={{styles.container}}>     // ✅
   <div className="container">              // ❌

3. Combine multiple classes:
   <div className={{`${{styles.btn}} ${{styles.primary}}`}}>  // ✅
   <div className={{styles.btn + ' ' + styles.primary}}>      // ✅

4. Add TypeScript support:
   // Create a Button.module.css.d.ts file:
   declare const styles: {{
     readonly container: string
     readonly button: string
   }}
   export default styles

5. Or use css-modules-typescript plugin:
   npm install --save-dev typescript-plugin-css-modules
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["css", "modules", "styling", "typescript"],
        ),
        # 9. Fix Async Component
        RemediationSkill(
            skill_id="fix_async_component",
            name="Fix Async Component Pattern",
            description="Correct async/await usage in components and effects",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"useEffect.*should not return anything besides a function",
                r"Cannot use 'await' outside of an async function",
                r"Objects are not valid as a React child",
            ],
            applicable_categories=["runtime_error", "build_error"],
            fix_template="""
At line {line_number} in {file_path}, fix async pattern:

1. Don't make useEffect async directly:
   ❌ useEffect(async () => {{ await fetchData() }}, [])

   ✅ useEffect(() => {{
     const loadData = async () => {{
       const data = await fetchData()
       setData(data)
     }}
     loadData()
   }}, [])

2. For Server Components (Next.js App Router):
   ✅ export default async function Page() {{
     const data = await fetchData()
     return <div>{{data}}</div>
   }}

3. Handle loading states:
   const [loading, setLoading] = useState(true)
   const [data, setData] = useState(null)

   useEffect(() => {{
     fetchData()
       .then(setData)
       .finally(() => setLoading(false))
   }}, [])

4. Clean up in useEffect:
   useEffect(() => {{
     let cancelled = false

     fetchData().then(data => {{
       if (!cancelled) setData(data)
     }})

     return () => {{ cancelled = true }}
   }}, [])

5. Use React Query/SWR for data fetching (recommended)
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "async", "useEffect", "promises"],
        ),
        # 10. Fix Context Usage
        RemediationSkill(
            skill_id="fix_context_usage",
            name="Fix React Context Usage",
            description="Correct Context API setup and consumption",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Cannot read.*of undefined.*useContext",
                r"useContext.*undefined",
                r"Context.*used outside of provider",
            ],
            applicable_categories=["runtime_error", "type_error"],
            fix_template="""
At line {line_number} in {file_path}, fix context usage:

1. Ensure Provider wraps component tree:
   ❌ <App /> without provider

   ✅ <ThemeProvider>
        <App />
      </ThemeProvider>

2. Define context with default value:
   const ThemeContext = createContext<ThemeType>({{
     theme: 'light',
     setTheme: () => {{}}
   }})

3. Use context correctly:
   const {{ theme, setTheme }} = useContext(ThemeContext)

4. Create custom hook for better DX:
   const useTheme = () => {{
     const context = useContext(ThemeContext)
     if (!context) {{
       throw new Error('useTheme must be used within ThemeProvider')
     }}
     return context
   }}

5. TypeScript: type the context:
   interface ThemeContextType {{
     theme: 'light' | 'dark'
     setTheme: (theme: 'light' | 'dark') => void
   }}

   const ThemeContext = createContext<ThemeContextType | undefined>(undefined)
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["react", "context", "hooks", "state"],
        ),
    ]

    # Add all skills to library
    for skill in skills:
        library.add_skill(skill)


def get_frontend_skill_count() -> int:
    """Get total number of frontend skills."""
    return 10
