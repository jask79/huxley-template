# iOS Navigation Architecture Patterns

**Complete reference for navigation, routing, and flow management in iOS apps**

---

## Overview

Navigation defines how users move through your app. This guide covers modern navigation patterns for both SwiftUI and UIKit, from basic push/pop to complex coordinator patterns and deep linking.

**Key Principles:**
- **Predictable** - Users should always know where they are
- **Reversible** - Easy to go back
- **Consistent** - Platform-standard navigation patterns
- **Deep Linkable** - Support universal links and URL schemes
- **State-Driven** - Navigation reflects app state

---

## Table of Contents

1. [SwiftUI Navigation](#swiftui-navigation)
2. [UIKit Navigation](#uikit-navigation)
3. [Navigation Patterns](#navigation-patterns)
4. [Deep Linking](#deep-linking)
5. [Coordinator Pattern](#coordinator-pattern)
6. [Tab Navigation](#tab-navigation)
7. [Modal Presentations](#modal-presentations)
8. [Split View Navigation](#split-view-navigation)
9. [Advanced Patterns](#advanced-patterns)

---

## SwiftUI Navigation

### NavigationStack (iOS 16+)

**Basic Navigation:**
```swift
struct ContentView: View {
    var body: some View {
        NavigationStack {
            List(1...20, id: \.self) { number in
                NavigationLink("Item \(number)", value: number)
            }
            .navigationTitle("Numbers")
            .navigationDestination(for: Int.self) { number in
                DetailView(number: number)
            }
        }
    }
}

struct DetailView: View {
    let number: Int

    var body: some View {
        Text("Detail for \(number)")
            .navigationTitle("Detail")
    }
}
```

**Programmatic Navigation:**
```swift
struct NavigationStackExample: View {
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            VStack {
                Button("Go to Detail") {
                    path.append("detail")
                }

                Button("Go to Settings") {
                    path.append("settings")
                }

                Button("Go Deep: Detail → Settings") {
                    path.append("detail")
                    path.append("settings")
                }

                Button("Pop to Root") {
                    path.removeLast(path.count)
                }
            }
            .navigationDestination(for: String.self) { destination in
                switch destination {
                case "detail":
                    DetailView()
                case "settings":
                    SettingsView()
                default:
                    Text("Unknown")
                }
            }
        }
    }
}
```

**Type-Safe Navigation Path:**
```swift
enum Destination: Hashable {
    case profile(userID: String)
    case settings
    case detail(itemID: Int)
}

struct TypeSafeNavigationExample: View {
    @State private var path: [Destination] = []

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Button("View Profile") {
                    path.append(.profile(userID: "user123"))
                }

                Button("Open Settings") {
                    path.append(.settings)
                }

                Button("View Detail") {
                    path.append(.detail(itemID: 42))
                }
            }
            .navigationTitle("Home")
            .navigationDestination(for: Destination.self) { destination in
                switch destination {
                case .profile(let userID):
                    ProfileView(userID: userID)

                case .settings:
                    SettingsView()

                case .detail(let itemID):
                    DetailView(itemID: itemID)
                }
            }
        }
    }
}
```

### NavigationLink Patterns

**Simple Navigation Link:**
```swift
NavigationLink("Go to Detail") {
    DetailView()
}
```

**NavigationLink with Value:**
```swift
// Define destination once
.navigationDestination(for: User.self) { user in
    UserProfileView(user: user)
}

// Use NavigationLink with value
NavigationLink("View User", value: user)
```

**Custom NavigationLink Styling:**
```swift
struct CustomNavigationLink: View {
    let title: String
    let destination: some View

    var body: some View {
        NavigationLink {
            destination
        } label: {
            HStack {
                Image(systemName: "arrow.right.circle")
                Text(title)
                Spacer()
                Image(systemName: "chevron.right")
                    .foregroundColor(.gray)
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(10)
        }
    }
}
```

### Navigation Bar Customization

**Title and Buttons:**
```swift
struct NavigationBarExample: View {
    var body: some View {
        NavigationStack {
            List {
                Text("Content")
            }
            .navigationTitle("My App")
            .navigationBarTitleDisplayMode(.large)  // .inline, .automatic
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        // Action
                    }
                }

                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        // Action
                    }
                }
            }
        }
    }
}
```

**Toolbar with Multiple Items:**
```swift
struct ToolbarExample: View {
    var body: some View {
        NavigationStack {
            Text("Content")
                .toolbar {
                    ToolbarItemGroup(placement: .navigationBarTrailing) {
                        Button(action: { /* search */ }) {
                            Image(systemName: "magnifyingglass")
                        }

                        Button(action: { /* filter */ }) {
                            Image(systemName: "line.3.horizontal.decrease.circle")
                        }

                        Button(action: { /* more */ }) {
                            Image(systemName: "ellipsis.circle")
                        }
                    }
                }
        }
    }
}
```

---

## UIKit Navigation

### UINavigationController

**Setup Navigation Controller:**
```swift
// In AppDelegate or SceneDelegate
let rootVC = HomeViewController()
let navigationController = UINavigationController(rootViewController: rootVC)
window?.rootViewController = navigationController
```

**Push View Controller:**
```swift
let detailVC = DetailViewController()
navigationController?.pushViewController(detailVC, animated: true)
```

**Pop View Controller:**
```swift
// Pop one
navigationController?.popViewController(animated: true)

// Pop to root
navigationController?.popToRootViewController(animated: true)

// Pop to specific VC
if let targetVC = navigationController?.viewControllers[1] {
    navigationController?.popToViewController(targetVC, animated: true)
}
```

**Programmatic Navigation:**
```swift
class HomeViewController: UIViewController {
    func navigateToDetail() {
        let detailVC = DetailViewController()
        detailVC.title = "Detail"
        navigationController?.pushViewController(detailVC, animated: true)
    }

    func navigateToSettings() {
        let settingsVC = SettingsViewController()
        navigationController?.pushViewController(settingsVC, animated: true)
    }
}
```

### Navigation Bar Customization

**Title and Buttons:**
```swift
class DetailViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()

        // Title
        title = "Detail"

        // Large title (iOS 11+)
        navigationController?.navigationBar.prefersLargeTitles = true
        navigationItem.largeTitleDisplayMode = .always  // .never, .automatic

        // Left bar button
        let cancelButton = UIBarButtonItem(
            title: "Cancel",
            style: .plain,
            target: self,
            action: #selector(cancelTapped)
        )
        navigationItem.leftBarButtonItem = cancelButton

        // Right bar button
        let doneButton = UIBarButtonItem(
            title: "Done",
            style: .done,
            target: self,
            action: #selector(doneTapped)
        )
        navigationItem.rightBarButtonItem = doneButton
    }

    @objc func cancelTapped() {
        navigationController?.popViewController(animated: true)
    }

    @objc func doneTapped() {
        // Save and pop
        navigationController?.popViewController(animated: true)
    }
}
```

**Multiple Bar Buttons:**
```swift
let searchButton = UIBarButtonItem(
    image: UIImage(systemName: "magnifyingglass"),
    style: .plain,
    target: self,
    action: #selector(searchTapped)
)

let filterButton = UIBarButtonItem(
    image: UIImage(systemName: "line.3.horizontal.decrease.circle"),
    style: .plain,
    target: self,
    action: #selector(filterTapped)
)

navigationItem.rightBarButtonItems = [filterButton, searchButton]
```

**Custom Navigation Bar Appearance:**
```swift
let appearance = UINavigationBarAppearance()
appearance.configureWithOpaqueBackground()
appearance.backgroundColor = .systemBlue
appearance.titleTextAttributes = [.foregroundColor: UIColor.white]
appearance.largeTitleTextAttributes = [.foregroundColor: UIColor.white]

navigationController?.navigationBar.standardAppearance = appearance
navigationController?.navigationBar.scrollEdgeAppearance = appearance
navigationController?.navigationBar.compactAppearance = appearance
```

---

## Navigation Patterns

### Hierarchical Navigation (Stack)

**When to use:**
- Drill-down interfaces (Settings → General → About)
- Master-detail flows
- Linear user flows (onboarding, checkout)

**SwiftUI Example:**
```swift
struct HierarchicalNavigation: View {
    var body: some View {
        NavigationStack {
            List {
                NavigationLink("Settings") {
                    SettingsView()
                }

                NavigationLink("Profile") {
                    ProfileView()
                }
            }
            .navigationTitle("Home")
        }
    }
}

struct SettingsView: View {
    var body: some View {
        List {
            NavigationLink("General") {
                GeneralSettingsView()
            }

            NavigationLink("Privacy") {
                PrivacySettingsView()
            }
        }
        .navigationTitle("Settings")
    }
}
```

### Flat Navigation (Tabs)

**When to use:**
- Top-level app sections
- Peer content areas
- 3-5 main sections

**SwiftUI Tab View:**
```swift
struct TabNavigationExample: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem {
                    Label("Home", systemImage: "house")
                }
                .tag(0)

            SearchView()
                .tabItem {
                    Label("Search", systemImage: "magnifyingglass")
                }
                .tag(1)

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person")
                }
                .tag(2)
        }
    }
}
```

**UIKit Tab Bar Controller:**
```swift
class MainTabBarController: UITabBarController {
    override func viewDidLoad() {
        super.viewDidLoad()

        let homeVC = UINavigationController(rootViewController: HomeViewController())
        homeVC.tabBarItem = UITabBarItem(
            title: "Home",
            image: UIImage(systemName: "house"),
            selectedImage: UIImage(systemName: "house.fill")
        )

        let searchVC = UINavigationController(rootViewController: SearchViewController())
        searchVC.tabBarItem = UITabBarItem(
            title: "Search",
            image: UIImage(systemName: "magnifyingglass"),
            tag: 1
        )

        let profileVC = UINavigationController(rootViewController: ProfileViewController())
        profileVC.tabBarItem = UITabBarItem(
            title: "Profile",
            image: UIImage(systemName: "person"),
            tag: 2
        )

        viewControllers = [homeVC, searchVC, profileVC]
    }
}
```

### Content-Driven Navigation

**When to use:**
- Non-linear exploration
- Search results
- Related content

**Example: Deep Navigation from Search:**
```swift
struct SearchView: View {
    @State private var path = NavigationPath()
    @State private var searchResults: [SearchResult] = []

    var body: some View {
        NavigationStack(path: $path) {
            List(searchResults) { result in
                Button(result.title) {
                    navigateToResult(result)
                }
            }
            .navigationTitle("Search")
            .navigationDestination(for: SearchResult.self) { result in
                ResultDetailView(result: result, path: $path)
            }
        }
    }

    func navigateToResult(_ result: SearchResult) {
        // Can navigate multiple levels deep based on result type
        switch result.type {
        case .user:
            path.append(result)

        case .post:
            // Navigate: Post → User
            path.append(result)
            path.append(result.author)

        case .comment:
            // Navigate: Comment → Post → User
            path.append(result.comment)
            path.append(result.post)
            path.append(result.author)
        }
    }
}
```

---

## Deep Linking

### Universal Links (HTTPS URLs)

**Setup Associated Domains:**
```swift
// Xcode: Signing & Capabilities → Add Capability → Associated Domains
// Add: applinks:yourdomain.com
```

**Handle Universal Links (SwiftUI):**
```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    handleDeepLink(url)
                }
        }
    }

    func handleDeepLink(_ url: URL) {
        guard url.scheme == "https",
              url.host == "yourdomain.com" else { return }

        let pathComponents = url.pathComponents

        // Parse URL: https://yourdomain.com/user/123
        if pathComponents.count >= 3,
           pathComponents[1] == "user",
           let userID = pathComponents[2] as String? {
            // Navigate to user profile
            navigateToUser(userID)
        }
    }

    func navigateToUser(_ userID: String) {
        // Update navigation state
        NotificationCenter.default.post(
            name: .deepLinkReceived,
            object: DeepLink.user(id: userID)
        )
    }
}
```

**Handle Universal Links (UIKit):**
```swift
// In AppDelegate or SceneDelegate
func application(
    _ application: UIApplication,
    continue userActivity: NSUserActivity,
    restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void
) -> Bool {
    guard userActivity.activityType == NSUserActivityTypeBrowsingWeb,
          let url = userActivity.webpageURL else {
        return false
    }

    handleDeepLink(url)
    return true
}

func handleDeepLink(_ url: URL) {
    let pathComponents = url.pathComponents

    // Parse URL and navigate
    if pathComponents.count >= 3,
       pathComponents[1] == "user" {
        let userID = pathComponents[2]
        navigateToUser(userID)
    }
}

func navigateToUser(_ userID: String) {
    let profileVC = ProfileViewController(userID: userID)

    if let tabBarController = window?.rootViewController as? UITabBarController,
       let navController = tabBarController.selectedViewController as? UINavigationController {
        navController.pushViewController(profileVC, animated: true)
    }
}
```

### Custom URL Schemes

**Setup URL Scheme:**
```swift
// Info.plist
// Add: URL types → Item 0 → URL Schemes → Item 0: "myapp"
```

**Handle Custom URL Scheme:**
```swift
// SwiftUI
.onOpenURL { url in
    if url.scheme == "myapp" {
        handleCustomURL(url)
    }
}

// UIKit (AppDelegate)
func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey : Any] = [:]
) -> Bool {
    if url.scheme == "myapp" {
        handleCustomURL(url)
        return true
    }
    return false
}

func handleCustomURL(_ url: URL) {
    // Parse: myapp://open?screen=profile&userID=123
    guard let components = URLComponents(url: url, resolvingAgainstBaseURL: true),
          let queryItems = components.queryItems else { return }

    let params = queryItems.reduce(into: [String: String]()) {
        $0[$1.name] = $1.value
    }

    if let screen = params["screen"] {
        switch screen {
        case "profile":
            if let userID = params["userID"] {
                navigateToUser(userID)
            }

        case "settings":
            navigateToSettings()

        default:
            break
        }
    }
}
```

---

## Coordinator Pattern

### Basic Coordinator (UIKit)

**Coordinator Protocol:**
```swift
protocol Coordinator: AnyObject {
    var childCoordinators: [Coordinator] { get set }
    var navigationController: UINavigationController { get set }

    func start()
}
```

**App Coordinator:**
```swift
class AppCoordinator: Coordinator {
    var childCoordinators = [Coordinator]()
    var navigationController: UINavigationController

    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }

    func start() {
        let homeVC = HomeViewController()
        homeVC.coordinator = self
        navigationController.pushViewController(homeVC, animated: false)
    }

    func showDetail(_ item: Item) {
        let detailVC = DetailViewController(item: item)
        detailVC.coordinator = self
        navigationController.pushViewController(detailVC, animated: true)
    }

    func showSettings() {
        let settingsCoordinator = SettingsCoordinator(navigationController: navigationController)
        childCoordinators.append(settingsCoordinator)
        settingsCoordinator.start()
    }
}
```

**View Controller with Coordinator:**
```swift
class HomeViewController: UIViewController {
    weak var coordinator: AppCoordinator?

    func didSelectItem(_ item: Item) {
        coordinator?.showDetail(item)
    }

    func didTapSettings() {
        coordinator?.showSettings()
    }
}
```

### FlowStacks Pattern (SwiftUI)

**FlowStacks Library:**
```swift
// Swift Package: https://github.com/johnpatrickmorgan/FlowStacks

import FlowStacks

enum Screen: Hashable {
    case home
    case detail(id: Int)
    case settings
}

struct CoordinatorView: View {
    @State private var routes: Routes<Screen> = [.root(.home)]

    var body: some View {
        Router($routes) { screen, _ in
            switch screen {
            case .home:
                HomeView(push: { screen in routes.push(screen) })

            case .detail(let id):
                DetailView(id: id, push: { screen in routes.push(screen) })

            case .settings:
                SettingsView(pop: { routes.goBack() })
            }
        }
    }
}

struct HomeView: View {
    let push: (Screen) -> Void

    var body: some View {
        Button("Go to Detail") {
            push(.detail(id: 1))
        }
    }
}
```

---

## Tab Navigation

### Custom Tab Bar (SwiftUI)

**Custom Tab Bar:**
```swift
struct CustomTabView: View {
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            // Content
            Group {
                switch selectedTab {
                case 0: HomeView()
                case 1: SearchView()
                case 2: ProfileView()
                default: HomeView()
                }
            }

            // Custom tab bar
            HStack {
                TabButton(title: "Home", imageName: "house", isSelected: selectedTab == 0) {
                    selectedTab = 0
                }

                TabButton(title: "Search", imageName: "magnifyingglass", isSelected: selectedTab == 1) {
                    selectedTab = 1
                }

                TabButton(title: "Profile", imageName: "person", isSelected: selectedTab == 2) {
                    selectedTab = 2
                }
            }
            .padding(.vertical, 8)
            .background(Color(.systemBackground))
            .shadow(color: .black.opacity(0.1), radius: 5, y: -5)
        }
    }
}

struct TabButton: View {
    let title: String
    let imageName: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: imageName)
                    .font(.system(size: 22))

                Text(title)
                    .font(.caption)
            }
            .foregroundColor(isSelected ? .blue : .gray)
            .frame(maxWidth: .infinity)
        }
    }
}
```

---

## Modal Presentations

### SwiftUI Sheets

**Basic Sheet:**
```swift
struct SheetExample: View {
    @State private var showingSheet = false

    var body: some View {
        Button("Show Sheet") {
            showingSheet = true
        }
        .sheet(isPresented: $showingSheet) {
            SheetContent()
        }
    }
}

struct SheetContent: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Text("Sheet Content")
                .navigationTitle("Modal")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Done") {
                            dismiss()
                        }
                    }
                }
        }
    }
}
```

**Sheet with Detents (iOS 16+):**
```swift
struct DetentSheetExample: View {
    @State private var showingSheet = false

    var body: some View {
        Button("Show Sheet") {
            showingSheet = true
        }
        .sheet(isPresented: $showingSheet) {
            SheetContent()
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
    }
}
```

**Full Screen Cover:**
```swift
struct FullScreenExample: View {
    @State private var showingFullScreen = false

    var body: some View {
        Button("Show Full Screen") {
            showingFullScreen = true
        }
        .fullScreenCover(isPresented: $showingFullScreen) {
            FullScreenContent()
        }
    }
}
```

### UIKit Modal Presentation

**Present View Controller:**
```swift
let detailVC = DetailViewController()
let navController = UINavigationController(rootViewController: detailVC)

// Presentation styles
navController.modalPresentationStyle = .automatic  // iOS 13+ (sheet)
// or .fullScreen, .pageSheet, .formSheet, .currentContext, .overFullScreen

// Transition styles
navController.modalTransitionStyle = .coverVertical
// or .flipHorizontal, .crossDissolve, .partialCurl

present(navController, animated: true)
```

**Custom Detents (iOS 15+):**
```swift
let detailVC = DetailViewController()

if let sheet = detailVC.sheetPresentationController {
    sheet.detents = [.medium(), .large()]
    sheet.prefersGrabberVisible = true
    sheet.prefersScrollingExpandsWhenScrolledToEdge = false
    sheet.prefersEdgeAttachedInCompactHeight = true
    sheet.widthFollowsPreferredContentSizeWhenEdgeAttached = true
}

present(detailVC, animated: true)
```

**Dismiss Modal:**
```swift
dismiss(animated: true)
```

---

## Split View Navigation

### SwiftUI Split View (iOS 16+)

**Three-Column Split:**
```swift
struct SplitViewExample: View {
    @State private var selectedCategory: Category?
    @State private var selectedItem: Item?

    var body: some View {
        NavigationSplitView {
            // Sidebar
            List(categories, selection: $selectedCategory) { category in
                NavigationLink(category.name, value: category)
            }
            .navigationTitle("Categories")
        } content: {
            // Content (middle column)
            if let category = selectedCategory {
                List(category.items, selection: $selectedItem) { item in
                    NavigationLink(item.name, value: item)
                }
                .navigationTitle(category.name)
            } else {
                Text("Select a category")
            }
        } detail: {
            // Detail
            if let item = selectedItem {
                DetailView(item: item)
            } else {
                Text("Select an item")
            }
        }
    }
}
```

### UIKit Split View Controller

**Three-Column Split:**
```swift
class SplitViewController: UISplitViewController {
    override func viewDidLoad() {
        super.viewDidLoad()

        preferredDisplayMode = .twoBesideSecondary
        presentsWithGesture = true

        // Sidebar
        let sidebarVC = SidebarViewController()
        let sidebarNav = UINavigationController(rootViewController: sidebarVC)

        // Content
        let contentVC = ContentViewController()
        let contentNav = UINavigationController(rootViewController: contentVC)

        // Detail
        let detailVC = DetailViewController()
        let detailNav = UINavigationController(rootViewController: detailVC)

        viewControllers = [sidebarNav, contentNav, detailNav]
    }
}
```

---

## Advanced Patterns

### State Restoration

**SwiftUI State Restoration:**
```swift
struct RestorationExample: View {
    @SceneStorage("selectedTab") private var selectedTab = 0
    @SceneStorage("navigationPath") private var navigationData: Data?

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                // Restore navigation path
                // ...
            }
            .tabItem { Label("Home", systemImage: "house") }
            .tag(0)
        }
    }
}
```

### Navigation Interception

**Confirm Before Navigation:**
```swift
struct InterceptionExample: View {
    @State private var showingAlert = false
    @State private var hasUnsavedChanges = true

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name", text: .constant(""))
            }
            .navigationBarBackButtonHidden(hasUnsavedChanges)
            .toolbar {
                if hasUnsavedChanges {
                    ToolbarItem(placement: .navigationBarLeading) {
                        Button("Cancel") {
                            showingAlert = true
                        }
                    }
                }
            }
            .alert("Unsaved Changes", isPresented: $showingAlert) {
                Button("Discard", role: .destructive) {
                    // Navigate back
                }
                Button("Cancel", role: .cancel) { }
            }
        }
    }
}
```

---

## Resources

**Apple Documentation:**
- [NavigationStack](https://developer.apple.com/documentation/swiftui/navigationstack)
- [UINavigationController](https://developer.apple.com/documentation/uikit/uinavigationcontroller)
- [Universal Links](https://developer.apple.com/ios/universal-links/)

**WWDC Videos:**
- WWDC 2022: "The SwiftUI cookbook for navigation"
- WWDC 2019: "Architecting Your App for Multiple Windows"

**Libraries:**
- [FlowStacks](https://github.com/johnpatrickmorgan/FlowStacks) - SwiftUI navigation coordinator
- [XCoordinator](https://github.com/quickbirdstudios/XCoordinator) - UIKit coordinator pattern

---

*iOS Navigation Architecture Patterns - Huxley Mobile Development*
*Building intuitive, maintainable navigation flows*
