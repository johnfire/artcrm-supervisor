# ArtCRM Mobile App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React Native (Expo) Android app with drawer navigation and 6 screens that connects to the ArtCRM backend API at https://crm.christopherrehm.de.

**Architecture:** Standalone repo `artcrm-mobile`. Expo managed workflow with Expo Router and drawer navigation. JWT stored in SecureStore. Axios API client with auth interceptor. Expo Notifications for push. All 6 screens are thin wrappers around REST API calls — no local state beyond auth token.

**Tech Stack:** Expo SDK 52, Expo Router, React Navigation Drawer, Axios, Expo SecureStore, Expo Notifications, TypeScript, Jest + React Native Testing Library

**Prerequisite:** The backend plan (`2026-06-01-artcrm-mobile-backend-api.md`) must be complete and deployed before the app can connect to a real server. Development can proceed against mock data.

---

## File Map

| Action | Path                                         | Responsibility                              |
| ------ | -------------------------------------------- | ------------------------------------------- |
| Create | `package.json`                               | dependencies                                |
| Create | `app.json`                                   | Expo config (app name, slug, notifications) |
| Create | `eas.json`                                   | EAS Build config                            |
| Create | `tsconfig.json`                              | TypeScript config                           |
| Create | `services/api.ts`                            | Axios client, all API calls                 |
| Create | `services/auth.ts`                           | JWT SecureStore helpers                     |
| Create | `services/notifications.ts`                  | Expo push token registration                |
| Create | `app/_layout.tsx`                            | Root layout — auth gate                     |
| Create | `app/login.tsx`                              | Login screen                                |
| Create | `app/(drawer)/_layout.tsx`                   | Drawer navigator with 6 items               |
| Create | `app/(drawer)/approvals.tsx`                 | Approvals list screen                       |
| Create | `app/(drawer)/inbox.tsx`                     | Inbox list screen                           |
| Create | `app/(drawer)/contacts.tsx`                  | Contacts list + search                      |
| Create | `app/(drawer)/contact-detail.tsx`            | Contact detail (pushed, not in drawer)      |
| Create | `app/(drawer)/activity.tsx`                  | Agent activity feed                         |
| Create | `app/(drawer)/marketing.tsx`                 | Marketing observations/strategies/digests   |
| Create | `app/(drawer)/research.tsx`                  | Trigger research scans                      |
| Create | `components/ApprovalCard.tsx`                | Draft card with approve/reject/edit actions |
| Create | `components/RejectSheet.tsx`                 | Bottom sheet for rejection reason           |
| Create | `components/InboxItem.tsx`                   | Inbox row with classification badge         |
| Create | `components/ClassifySheet.tsx`               | Bottom sheet for inbox classification       |
| Create | `components/ContactRow.tsx`                  | Contact list row with score badge           |
| Create | `components/ActivityItem.tsx`                | Agent run row                               |
| Create | `__tests__/services/api.test.ts`             | API service unit tests                      |
| Create | `__tests__/services/auth.test.ts`            | Auth service unit tests                     |
| Create | `__tests__/components/ApprovalCard.test.tsx` | Component tests                             |

---

## Task 1: Scaffold the Expo project

- [ ] **Step 1: Create the project**

From the parent directory of `artcrm-supervisor` (i.e. `~/ppp2/artcrm/`):

```bash
npx create-expo-app@latest artcrm-mobile --template blank-typescript
cd artcrm-mobile
```

- [ ] **Step 2: Install core dependencies**

```bash
npx expo install expo-router expo-secure-store expo-notifications expo-device expo-constants
npx expo install @react-navigation/drawer react-native-gesture-handler react-native-reanimated
npm install axios
npm install --save-dev @testing-library/react-native @testing-library/jest-native jest-expo
```

- [ ] **Step 3: Verify the project runs**

```bash
npx expo start
```

Press `a` to open Android emulator. Expected: blank white screen with "Open up App.tsx to start working on your app!" — or equivalent blank screen.

Press `Ctrl+C` to stop.

- [ ] **Step 4: Init git**

```bash
git init
echo "node_modules/\n.expo/\ndist/\n*.orig.*\n.env" > .gitignore
git add .
git commit -m "chore: scaffold Expo project"
```

---

## Task 2: Configure app.json, tsconfig, and package.json scripts

**Files:**

- Modify: `app.json`
- Modify: `tsconfig.json`
- Create: `eas.json`

- [ ] **Step 1: Update app.json**

Replace the contents of `app.json`:

```json
{
  "expo": {
    "name": "ArtCRM",
    "slug": "artcrm-mobile",
    "version": "1.0.0",
    "orientation": "portrait",
    "scheme": "artcrm",
    "userInterfaceStyle": "dark",
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/images/adaptive-icon.png",
        "backgroundColor": "#1a1a2e"
      },
      "package": "de.christopherrehm.artcrm"
    },
    "plugins": [
      "expo-router",
      [
        "expo-notifications",
        {
          "icon": "./assets/images/notification-icon.png",
          "color": "#7c6fff"
        }
      ]
    ],
    "experiments": {
      "typedRoutes": true
    }
  }
}
```

- [ ] **Step 2: Update tsconfig.json**

Replace the contents of `tsconfig.json`:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "paths": {
      "@/*": ["./*"]
    }
  }
}
```

- [ ] **Step 3: Create eas.json**

Create `eas.json`:

```json
{
  "cli": {
    "version": ">= 10.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "android": {
        "buildType": "app-bundle"
      }
    }
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add app.json tsconfig.json eas.json
git commit -m "chore: configure Expo app and EAS build"
```

---

## Task 3: API service layer

**Files:**

- Create: `services/api.ts`
- Create: `__tests__/services/api.test.ts`

- [ ] **Step 1: Write failing tests**

Create `__tests__/services/api.test.ts`:

```typescript
import { buildHeaders, API_BASE } from "../../services/api";

describe("api service", () => {
  it("uses the correct base URL", () => {
    expect(API_BASE).toBe("https://crm.christopherrehm.de");
  });

  it("buildHeaders includes Authorization when token provided", () => {
    const headers = buildHeaders("my-jwt-token");
    expect(headers["Authorization"]).toBe("Bearer my-jwt-token");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("buildHeaders works without token", () => {
    const headers = buildHeaders(null);
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Authorization"]).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run to verify fail**

```bash
npx jest __tests__/services/api.test.ts
```

Expected: `Cannot find module '../../services/api'`

- [ ] **Step 3: Create services/api.ts**

Create `services/api.ts`:

```typescript
import axios from "axios";
import { getToken } from "./auth";

export const API_BASE = "https://crm.christopherrehm.de";

export function buildHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

const client = axios.create({ baseURL: API_BASE });

client.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) config.headers["Authorization"] = `Bearer ${token}`;
  return config;
});

// --- Auth ---
export async function login(
  password: string,
): Promise<{ token: string; role: string }> {
  const resp = await client.post("/api/auth/token", { password });
  return resp.data;
}

// --- Push ---
export async function registerPushToken(pushToken: string): Promise<void> {
  await client.post("/api/push/register", { token: pushToken });
}

// --- Approvals ---
export async function fetchApprovals(): Promise<Approval[]> {
  const resp = await client.get("/api/approvals");
  return resp.data;
}
export async function approveEmail(id: number): Promise<void> {
  await client.post(`/api/approvals/${id}/approve`);
}
export async function rejectEmail(id: number, reason: string): Promise<void> {
  await client.post(`/api/approvals/${id}/reject`, { reason });
}

// --- Inbox ---
export async function fetchInbox(): Promise<InboxMessage[]> {
  const resp = await client.get("/api/inbox");
  return resp.data;
}
export async function classifyMessage(
  id: number,
  classification: string,
): Promise<void> {
  await client.post(`/api/inbox/${id}/classify`, { classification });
}

// --- Contacts ---
export async function fetchContacts(params: {
  search?: string;
  status?: string;
  page?: number;
}): Promise<Contact[]> {
  const resp = await client.get("/api/contacts", { params });
  return resp.data;
}
export async function fetchContact(id: number): Promise<ContactDetail> {
  const resp = await client.get(`/api/contacts/${id}`);
  return resp.data;
}

// --- Activity ---
export async function fetchActivity(): Promise<AgentRun[]> {
  const resp = await client.get("/api/activity");
  return resp.data;
}

// --- Marketing ---
export async function fetchObservations(): Promise<MarketingItem[]> {
  const resp = await client.get("/api/marketing/observations");
  return resp.data;
}
export async function fetchStrategies(): Promise<MarketingItem[]> {
  const resp = await client.get("/api/marketing/strategies");
  return resp.data;
}
export async function fetchDigests(): Promise<MarketingItem[]> {
  const resp = await client.get("/api/marketing/digests");
  return resp.data;
}

// --- Research ---
export async function runResearch(
  city: string,
  level: number,
  country = "DE",
): Promise<void> {
  await client.post("/api/research/run", { city, level, country });
}

// --- Types ---
export interface Approval {
  id: number;
  draft_subject: string;
  draft_body: string;
  created_at: string;
  contact_id: number;
  name: string;
  city: string;
  email: string;
}

export interface InboxMessage {
  id: number;
  from_email: string;
  subject: string;
  body: string;
  received_at: string;
  classification: string | null;
  contact_id: number | null;
  contact_name: string | null;
  city: string | null;
}

export interface Contact {
  id: number;
  name: string;
  city: string;
  country: string;
  type: string;
  status: string;
  email: string | null;
  website: string | null;
  fit_score: number | null;
  flagged: boolean;
  last_contact: string | null;
}

export interface ContactDetail extends Contact {
  phone: string | null;
  notes: string | null;
  neighborhood: string | null;
  visit_when_nearby: boolean;
  interactions: Interaction[];
}

export interface Interaction {
  interaction_type: string;
  interaction_date: string;
  notes: string | null;
}

export interface AgentRun {
  id: number;
  agent_name: string;
  status: "running" | "completed" | "failed";
  summary: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface MarketingItem {
  id: number;
  [key: string]: unknown;
}
```

- [ ] **Step 4: Run tests**

```bash
npx jest __tests__/services/api.test.ts
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api.ts __tests__/services/api.test.ts
git commit -m "feat: add API service layer with all endpoints and types"
```

---

## Task 4: Auth service

**Files:**

- Create: `services/auth.ts`
- Create: `__tests__/services/auth.test.ts`

- [ ] **Step 1: Write failing tests**

Create `__tests__/services/auth.test.ts`:

```typescript
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import * as SecureStore from "expo-secure-store";
import { getToken, saveToken, clearToken } from "../../services/auth";

const mockGet = SecureStore.getItemAsync as jest.Mock;
const mockSet = SecureStore.setItemAsync as jest.Mock;
const mockDel = SecureStore.deleteItemAsync as jest.Mock;

describe("auth service", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getToken returns null when nothing stored", async () => {
    mockGet.mockResolvedValue(null);
    expect(await getToken()).toBeNull();
  });

  it("getToken returns stored token", async () => {
    mockGet.mockResolvedValue("my-token");
    expect(await getToken()).toBe("my-token");
  });

  it("saveToken stores token and role", async () => {
    mockSet.mockResolvedValue(undefined);
    await saveToken("my-token", "admin");
    expect(mockSet).toHaveBeenCalledWith("artcrm_jwt", "my-token");
    expect(mockSet).toHaveBeenCalledWith("artcrm_role", "admin");
  });

  it("clearToken deletes both keys", async () => {
    mockDel.mockResolvedValue(undefined);
    await clearToken();
    expect(mockDel).toHaveBeenCalledWith("artcrm_jwt");
    expect(mockDel).toHaveBeenCalledWith("artcrm_role");
  });
});
```

- [ ] **Step 2: Run to verify fail**

```bash
npx jest __tests__/services/auth.test.ts
```

Expected: `Cannot find module '../../services/auth'`

- [ ] **Step 3: Create services/auth.ts**

Create `services/auth.ts`:

```typescript
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "artcrm_jwt";
const ROLE_KEY = "artcrm_role";

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function getRole(): Promise<string | null> {
  return SecureStore.getItemAsync(ROLE_KEY);
}

export async function saveToken(token: string, role: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  await SecureStore.setItemAsync(ROLE_KEY, role);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(ROLE_KEY);
}

export async function isLoggedIn(): Promise<boolean> {
  const token = await getToken();
  return token !== null;
}
```

- [ ] **Step 4: Run tests**

```bash
npx jest __tests__/services/auth.test.ts
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/auth.ts __tests__/services/auth.test.ts
git commit -m "feat: add auth service with SecureStore"
```

---

## Task 5: Notifications service

**Files:**

- Create: `services/notifications.ts`

- [ ] **Step 1: Create services/notifications.ts**

Create `services/notifications.ts`:

```typescript
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { registerPushToken } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications(): Promise<void> {
  if (!Device.isDevice) return; // skip in emulator

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== "granted") return;

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "default",
      importance: Notifications.AndroidImportance.MAX,
    });
  }

  const token = (await Notifications.getExpoPushTokenAsync()).data;
  await registerPushToken(token);
}
```

- [ ] **Step 2: Commit**

```bash
git add services/notifications.ts
git commit -m "feat: add push notification registration service"
```

---

## Task 6: Root layout and auth gate

**Files:**

- Create: `app/_layout.tsx`

- [ ] **Step 1: Create app/\_layout.tsx**

Create `app/_layout.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { isLoggedIn } from '../services/auth';
import { registerForPushNotifications } from '../services/notifications';

export default function RootLayout() {
  const router = useRouter();
  const segments = useSegments();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    isLoggedIn().then((loggedIn) => {
      setChecked(true);
      const inDrawer = segments[0] === '(drawer)';
      if (!loggedIn && inDrawer) {
        router.replace('/login');
      } else if (loggedIn && !inDrawer) {
        router.replace('/(drawer)/approvals');
      }
    });
  }, []);

  useEffect(() => {
    if (checked) registerForPushNotifications();
  }, [checked]);

  if (!checked) return null;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="login" />
      <Stack.Screen name="(drawer)" />
    </Stack>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add app/_layout.tsx
git commit -m "feat: add root layout with auth gate"
```

---

## Task 7: Login screen

**Files:**

- Create: `app/login.tsx`

- [ ] **Step 1: Create app/login.tsx**

Create `app/login.tsx`:

```typescript
import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, ActivityIndicator, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { login } from '../services/api';
import { saveToken } from '../services/auth';

export default function LoginScreen() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!password.trim()) return;
    setLoading(true);
    try {
      const { token, role } = await login(password.trim());
      await saveToken(token, role);
      router.replace('/(drawer)/approvals');
    } catch {
      Alert.alert('Login failed', 'Wrong password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView style={s.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Text style={s.title}>ArtCRM</Text>
      <Text style={s.subtitle}>Sign in to continue</Text>
      <TextInput
        style={s.input}
        placeholder="Password"
        placeholderTextColor="#555"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        onSubmitEditing={handleLogin}
        returnKeyType="go"
        autoFocus
      />
      <TouchableOpacity style={s.button} onPress={handleLogin} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Sign In</Text>}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23', justifyContent: 'center', padding: 32 },
  title: { fontSize: 32, fontWeight: '700', color: '#fff', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#888', marginBottom: 40 },
  input: {
    backgroundColor: '#1a1a2e', color: '#fff', borderRadius: 10,
    padding: 16, fontSize: 16, marginBottom: 16,
    borderWidth: 1, borderColor: '#ffffff20',
  },
  button: {
    backgroundColor: '#7c6fff', borderRadius: 10,
    padding: 16, alignItems: 'center',
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
```

- [ ] **Step 2: Commit**

```bash
git add app/login.tsx
git commit -m "feat: add login screen"
```

---

## Task 8: Drawer navigator shell

**Files:**

- Create: `app/(drawer)/_layout.tsx`

- [ ] **Step 1: Create the drawer layout**

Create `app/(drawer)/_layout.tsx`:

```typescript
import { Drawer } from 'expo-router/drawer';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { clearToken } from '../../services/auth';

function LogoutButton() {
  const router = useRouter();
  async function handleLogout() {
    await clearToken();
    router.replace('/login');
  }
  return (
    <TouchableOpacity onPress={handleLogout} style={{ padding: 16 }}>
      <Text style={{ color: '#ef4444', fontSize: 14 }}>Log out</Text>
    </TouchableOpacity>
  );
}

export default function DrawerLayout() {
  return (
    <Drawer
      screenOptions={{
        headerStyle: { backgroundColor: '#0f0f23' },
        headerTintColor: '#fff',
        drawerStyle: { backgroundColor: '#0f0f23' },
        drawerActiveTintColor: '#7c6fff',
        drawerInactiveTintColor: '#888',
        drawerLabelStyle: { fontSize: 15 },
        headerRight: () => <LogoutButton />,
      }}
    >
      <Drawer.Screen name="approvals" options={{ title: 'Approvals', drawerLabel: '✓  Approvals' }} />
      <Drawer.Screen name="inbox" options={{ title: 'Inbox', drawerLabel: '✉  Inbox' }} />
      <Drawer.Screen name="contacts" options={{ title: 'Contacts', drawerLabel: '👤  Contacts' }} />
      <Drawer.Screen name="activity" options={{ title: 'Activity', drawerLabel: '⚡  Activity' }} />
      <Drawer.Screen name="marketing" options={{ title: 'Marketing', drawerLabel: '📊  Marketing' }} />
      <Drawer.Screen name="research" options={{ title: 'Research', drawerLabel: '🔍  Research' }} />
      <Drawer.Screen name="contact-detail" options={{ drawerItemStyle: { display: 'none' }, title: 'Contact' }} />
    </Drawer>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "app/(drawer)/_layout.tsx"
git commit -m "feat: add drawer navigation shell with logout"
```

---

## Task 9: Approvals screen and components

**Files:**

- Create: `components/RejectSheet.tsx`
- Create: `components/ApprovalCard.tsx`
- Create: `app/(drawer)/approvals.tsx`
- Create: `__tests__/components/ApprovalCard.test.tsx`

- [ ] **Step 1: Create RejectSheet.tsx**

Create `components/RejectSheet.tsx`:

```typescript
import { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform,
} from 'react-native';

interface Props {
  visible: boolean;
  venueName: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function RejectSheet({ visible, venueName, onConfirm, onCancel }: Props) {
  const [reason, setReason] = useState('');

  function handleConfirm() {
    onConfirm(reason.trim());
    setReason('');
  }

  return (
    <Modal visible={visible} transparent animationType="slide">
      <KeyboardAvoidingView style={s.overlay} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={s.sheet}>
          <Text style={s.title}>Reject draft</Text>
          <Text style={s.subtitle}>{venueName}</Text>
          <Text style={s.label}>Reason (optional)</Text>
          <TextInput
            style={s.input}
            placeholder="e.g. Too formal, needs warmer tone"
            placeholderTextColor="#555"
            value={reason}
            onChangeText={setReason}
            multiline
            autoFocus
          />
          <View style={s.row}>
            <TouchableOpacity style={s.cancelBtn} onPress={onCancel}>
              <Text style={s.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.confirmBtn} onPress={handleConfirm}>
              <Text style={s.confirmText}>Confirm Reject</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: '#00000088' },
  sheet: { backgroundColor: '#1e1e3a', borderRadius: 16, padding: 20, margin: 8 },
  title: { color: '#fff', fontSize: 16, fontWeight: '700', marginBottom: 4 },
  subtitle: { color: '#888', fontSize: 13, marginBottom: 16 },
  label: { color: '#888', fontSize: 12, marginBottom: 6 },
  input: {
    backgroundColor: '#ffffff10', color: '#fff', borderRadius: 8,
    padding: 12, fontSize: 14, minHeight: 80, marginBottom: 16,
  },
  row: { flexDirection: 'row', gap: 10 },
  cancelBtn: { flex: 1, backgroundColor: '#ffffff10', borderRadius: 8, padding: 12, alignItems: 'center' },
  cancelText: { color: '#aaa', fontWeight: '600' },
  confirmBtn: { flex: 1, backgroundColor: '#ef4444', borderRadius: 8, padding: 12, alignItems: 'center' },
  confirmText: { color: '#fff', fontWeight: '700' },
});
```

- [ ] **Step 2: Write failing component test**

Create `__tests__/components/ApprovalCard.test.tsx`:

```typescript
import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { ApprovalCard } from '../../components/ApprovalCard';
import { Approval } from '../../services/api';

const mockApproval: Approval = {
  id: 1,
  draft_subject: 'Test Subject',
  draft_body: 'Hello World body text',
  created_at: '2026-06-01T10:00:00Z',
  contact_id: 42,
  name: 'Galerie Test',
  city: 'München',
  email: 'test@galerie.de',
};

describe('ApprovalCard', () => {
  it('renders venue name and subject', () => {
    const { getByText } = render(
      <ApprovalCard
        item={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );
    expect(getByText('Galerie Test, München')).toBeTruthy();
    expect(getByText('Test Subject')).toBeTruthy();
  });

  it('calls onApprove when Approve tapped', () => {
    const onApprove = jest.fn();
    const { getByText } = render(
      <ApprovalCard item={mockApproval} onApprove={onApprove} onReject={jest.fn()} onEdit={jest.fn()} />
    );
    fireEvent.press(getByText('Approve'));
    expect(onApprove).toHaveBeenCalledWith(1);
  });

  it('calls onReject when Reject tapped', () => {
    const onReject = jest.fn();
    const { getByText } = render(
      <ApprovalCard item={mockApproval} onApprove={jest.fn()} onReject={onReject} onEdit={jest.fn()} />
    );
    fireEvent.press(getByText('Reject'));
    expect(onReject).toHaveBeenCalledWith(mockApproval);
  });
});
```

- [ ] **Step 3: Run to verify fail**

```bash
npx jest __tests__/components/ApprovalCard.test.tsx
```

Expected: `Cannot find module '../../components/ApprovalCard'`

- [ ] **Step 4: Create ApprovalCard.tsx**

Create `components/ApprovalCard.tsx`:

```typescript
import { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal, ScrollView } from 'react-native';
import { Approval } from '../services/api';

interface Props {
  item: Approval;
  onApprove: (id: number) => void;
  onReject: (item: Approval) => void;
  onEdit: (item: Approval) => void;
}

export function ApprovalCard({ item, onApprove, onReject, onEdit }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <TouchableOpacity style={s.card} onPress={() => setExpanded(true)} activeOpacity={0.8}>
        <Text style={s.venue}>{item.name}, {item.city}</Text>
        <Text style={s.subject}>{item.draft_subject}</Text>
        <Text style={s.preview} numberOfLines={2}>{item.draft_body}</Text>
        <View style={s.actions}>
          <TouchableOpacity style={s.approveBtn} onPress={() => onApprove(item.id)}>
            <Text style={s.approveTxt}>Approve</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.rejectBtn} onPress={() => onReject(item)}>
            <Text style={s.rejectTxt}>Reject</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.editBtn} onPress={() => onEdit(item)}>
            <Text style={s.editTxt}>Edit</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>

      <Modal visible={expanded} animationType="slide">
        <View style={s.modal}>
          <Text style={s.modalTitle}>{item.draft_subject}</Text>
          <Text style={s.modalVenue}>{item.name} · {item.city}</Text>
          <ScrollView style={s.bodyScroll}>
            <Text style={s.bodyText}>{item.draft_body}</Text>
          </ScrollView>
          <TouchableOpacity style={s.closeBtn} onPress={() => setExpanded(false)}>
            <Text style={s.closeTxt}>Close</Text>
          </TouchableOpacity>
        </View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  card: { backgroundColor: '#1a1a2e', borderRadius: 12, padding: 16, marginBottom: 12 },
  venue: { color: '#fff', fontSize: 14, fontWeight: '700', marginBottom: 4 },
  subject: { color: '#aaa', fontSize: 13, marginBottom: 6 },
  preview: { color: '#666', fontSize: 12, lineHeight: 18, marginBottom: 12 },
  actions: { flexDirection: 'row', gap: 8 },
  approveBtn: { flex: 1, backgroundColor: '#22c55e20', borderRadius: 6, padding: 8, alignItems: 'center', borderWidth: 1, borderColor: '#22c55e50' },
  approveTxt: { color: '#22c55e', fontSize: 12, fontWeight: '600' },
  rejectBtn: { flex: 1, backgroundColor: '#ef444420', borderRadius: 6, padding: 8, alignItems: 'center', borderWidth: 1, borderColor: '#ef444450' },
  rejectTxt: { color: '#ef4444', fontSize: 12, fontWeight: '600' },
  editBtn: { flex: 1, backgroundColor: '#ffffff10', borderRadius: 6, padding: 8, alignItems: 'center' },
  editTxt: { color: '#aaa', fontSize: 12, fontWeight: '600' },
  modal: { flex: 1, backgroundColor: '#0f0f23', padding: 24, paddingTop: 60 },
  modalTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginBottom: 4 },
  modalVenue: { color: '#888', fontSize: 13, marginBottom: 20 },
  bodyScroll: { flex: 1 },
  bodyText: { color: '#ccc', fontSize: 15, lineHeight: 24 },
  closeBtn: { backgroundColor: '#ffffff10', borderRadius: 10, padding: 16, alignItems: 'center', marginTop: 16 },
  closeTxt: { color: '#fff', fontSize: 15, fontWeight: '600' },
});
```

- [ ] **Step 5: Run tests**

```bash
npx jest __tests__/components/ApprovalCard.test.tsx
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Create the Approvals screen**

Create `app/(drawer)/approvals.tsx`:

```typescript
import { useState, useCallback } from 'react';
import {
  View, FlatList, Text, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { fetchApprovals, approveEmail, rejectEmail, Approval } from '../../services/api';
import { ApprovalCard } from '../../components/ApprovalCard';
import { RejectSheet } from '../../components/RejectSheet';

export default function ApprovalsScreen() {
  const [items, setItems] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectTarget, setRejectTarget] = useState<Approval | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchApprovals());
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function handleApprove(id: number) {
    await approveEmail(id);
    setItems((prev) => prev.filter((a) => a.id !== id));
  }

  async function handleReject(item: Approval) {
    setRejectTarget(item);
  }

  async function confirmReject(reason: string) {
    if (!rejectTarget) return;
    await rejectEmail(rejectTarget.id, reason);
    setItems((prev) => prev.filter((a) => a.id !== rejectTarget.id));
    setRejectTarget(null);
  }

  if (loading) return <View style={s.center}><ActivityIndicator color="#7c6fff" /></View>;

  return (
    <View style={s.container}>
      <FlatList
        data={items}
        keyExtractor={(a) => String(a.id)}
        renderItem={({ item }) => (
          <ApprovalCard
            item={item}
            onApprove={handleApprove}
            onReject={handleReject}
            onEdit={() => {/* edit flow — future */}}
          />
        )}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#7c6fff" />}
        contentContainerStyle={s.list}
        ListEmptyComponent={<Text style={s.empty}>No pending approvals</Text>}
      />
      <RejectSheet
        visible={!!rejectTarget}
        venueName={rejectTarget ? `${rejectTarget.name}, ${rejectTarget.city}` : ''}
        onConfirm={confirmReject}
        onCancel={() => setRejectTarget(null)}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  list: { padding: 16 },
  center: { flex: 1, backgroundColor: '#0f0f23', justifyContent: 'center', alignItems: 'center' },
  empty: { color: '#555', textAlign: 'center', marginTop: 60, fontSize: 15 },
});
```

- [ ] **Step 7: Commit**

```bash
git add components/ApprovalCard.tsx components/RejectSheet.tsx "app/(drawer)/approvals.tsx" "__tests__/components/ApprovalCard.test.tsx"
git commit -m "feat: add Approvals screen with approve/reject/reason flow"
```

---

## Task 10: Inbox screen

**Files:**

- Create: `components/ClassifySheet.tsx`
- Create: `app/(drawer)/inbox.tsx`

- [ ] **Step 1: Create ClassifySheet.tsx**

Create `components/ClassifySheet.tsx`:

```typescript
import { Modal, View, Text, TouchableOpacity, StyleSheet } from 'react-native';

const CLASSIFICATIONS = [
  { key: 'interested', label: 'Interested', color: '#22c55e' },
  { key: 'warm', label: 'Warm / Considering', color: '#84cc16' },
  { key: 'not_interested', label: 'Not Interested', color: '#ef4444' },
  { key: 'opt_out', label: 'Opt Out', color: '#dc2626' },
  { key: 'auto_reply', label: 'Auto Reply', color: '#888' },
  { key: 'bounced', label: 'Bounced', color: '#888' },
];

interface Props {
  visible: boolean;
  onSelect: (classification: string) => void;
  onCancel: () => void;
}

export function ClassifySheet({ visible, onSelect, onCancel }: Props) {
  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={s.overlay}>
        <View style={s.sheet}>
          <Text style={s.title}>Classify reply</Text>
          {CLASSIFICATIONS.map((c) => (
            <TouchableOpacity key={c.key} style={s.option} onPress={() => onSelect(c.key)}>
              <Text style={[s.optionText, { color: c.color }]}>{c.label}</Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity style={s.cancelBtn} onPress={onCancel}>
            <Text style={s.cancelText}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: '#00000088' },
  sheet: { backgroundColor: '#1e1e3a', borderRadius: 16, padding: 20, margin: 8 },
  title: { color: '#fff', fontSize: 16, fontWeight: '700', marginBottom: 16 },
  option: { padding: 14, borderBottomWidth: 1, borderBottomColor: '#ffffff10' },
  optionText: { fontSize: 15, fontWeight: '600' },
  cancelBtn: { marginTop: 12, padding: 14, alignItems: 'center', backgroundColor: '#ffffff10', borderRadius: 8 },
  cancelText: { color: '#aaa', fontSize: 15, fontWeight: '600' },
});
```

- [ ] **Step 2: Create app/(drawer)/inbox.tsx**

Create `app/(drawer)/inbox.tsx`:

```typescript
import { useState, useCallback } from 'react';
import { View, FlatList, Text, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { fetchInbox, classifyMessage, InboxMessage } from '../../services/api';
import { ClassifySheet } from '../../components/ClassifySheet';

const CLASSIFICATION_COLOR: Record<string, string> = {
  interested: '#22c55e',
  warm: '#84cc16',
  not_interested: '#ef4444',
  opt_out: '#dc2626',
  auto_reply: '#888',
  bounced: '#888',
};

export default function InboxScreen() {
  const [items, setItems] = useState<InboxMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [classifyTarget, setClassifyTarget] = useState<InboxMessage | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setItems(await fetchInbox()); } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function handleClassify(classification: string) {
    if (!classifyTarget) return;
    await classifyMessage(classifyTarget.id, classification);
    setItems((prev) =>
      prev.map((m) => m.id === classifyTarget.id ? { ...m, classification } : m)
    );
    setClassifyTarget(null);
  }

  if (loading) return <View style={s.center}><ActivityIndicator color="#7c6fff" /></View>;

  return (
    <View style={s.container}>
      <FlatList
        data={items}
        keyExtractor={(m) => String(m.id)}
        renderItem={({ item }) => {
          const color = item.classification
            ? CLASSIFICATION_COLOR[item.classification] ?? '#888'
            : '#444';
          return (
            <View style={[s.item, { borderLeftColor: color }]}>
              <Text style={s.from}>{item.contact_name ?? item.from_email}</Text>
              <Text style={s.subject}>{item.subject}</Text>
              <Text style={s.body} numberOfLines={2}>{item.body}</Text>
              <TouchableOpacity style={[s.badge, { borderColor: color }]} onPress={() => setClassifyTarget(item)}>
                <Text style={[s.badgeText, { color }]}>
                  {item.classification ?? 'Classify ▾'}
                </Text>
              </TouchableOpacity>
            </View>
          );
        }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#7c6fff" />}
        contentContainerStyle={s.list}
        ListEmptyComponent={<Text style={s.empty}>Inbox is empty</Text>}
      />
      <ClassifySheet
        visible={!!classifyTarget}
        onSelect={handleClassify}
        onCancel={() => setClassifyTarget(null)}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  list: { padding: 16 },
  center: { flex: 1, backgroundColor: '#0f0f23', justifyContent: 'center', alignItems: 'center' },
  item: { backgroundColor: '#1a1a2e', borderRadius: 10, padding: 14, marginBottom: 10, borderLeftWidth: 3 },
  from: { color: '#fff', fontSize: 13, fontWeight: '700', marginBottom: 2 },
  subject: { color: '#aaa', fontSize: 12, marginBottom: 6 },
  body: { color: '#666', fontSize: 12, lineHeight: 18, marginBottom: 10 },
  badge: { alignSelf: 'flex-start', borderWidth: 1, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3 },
  badgeText: { fontSize: 11, fontWeight: '600' },
  empty: { color: '#555', textAlign: 'center', marginTop: 60, fontSize: 15 },
});
```

- [ ] **Step 3: Commit**

```bash
git add components/ClassifySheet.tsx "app/(drawer)/inbox.tsx"
git commit -m "feat: add Inbox screen with classification sheet"
```

---

## Task 11: Contacts screen and detail

**Files:**

- Create: `components/ContactRow.tsx`
- Create: `app/(drawer)/contacts.tsx`
- Create: `app/(drawer)/contact-detail.tsx`

- [ ] **Step 1: Create ContactRow.tsx**

Create `components/ContactRow.tsx`:

```typescript
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Contact } from '../services/api';

interface Props {
  item: Contact;
  onPress: (id: number) => void;
}

function scoreBadgeColor(score: number | null) {
  if (!score) return '#444';
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#eab308';
  return '#888';
}

export function ContactRow({ item, onPress }: Props) {
  const color = scoreBadgeColor(item.fit_score);
  return (
    <TouchableOpacity style={s.row} onPress={() => onPress(item.id)}>
      <View style={s.info}>
        <Text style={s.name}>{item.name}</Text>
        <Text style={s.sub}>{item.city} · {item.type}</Text>
      </View>
      {item.fit_score !== null && (
        <View style={[s.badge, { backgroundColor: color + '25', borderColor: color + '80' }]}>
          <Text style={[s.badgeText, { color }]}>{item.fit_score}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1a1a2e', borderRadius: 10, padding: 14, marginBottom: 8 },
  info: { flex: 1 },
  name: { color: '#fff', fontSize: 14, fontWeight: '600', marginBottom: 2 },
  sub: { color: '#888', fontSize: 12 },
  badge: { borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1 },
  badgeText: { fontSize: 12, fontWeight: '700' },
});
```

- [ ] **Step 2: Create contacts.tsx**

Create `app/(drawer)/contacts.tsx`:

```typescript
import { useState, useCallback } from 'react';
import {
  View, FlatList, TextInput, Text, TouchableOpacity,
  StyleSheet, ActivityIndicator, RefreshControl, ScrollView,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { fetchContacts, Contact } from '../../services/api';
import { ContactRow } from '../../components/ContactRow';

const STATUS_FILTERS = ['', 'cold', 'contacted', 'meeting', 'proposal', 'accepted', 'rejected', 'dropped'];
const STATUS_LABELS: Record<string, string> = {
  '': 'All', cold: 'Cold', contacted: 'Contacted', meeting: 'Meeting',
  proposal: 'Proposal', accepted: 'Accepted', rejected: 'Rejected', dropped: 'Dropped',
};

export default function ContactsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try { setItems(await fetchContacts({ search, status })); } finally { setLoading(false); }
  }, [search, status]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={s.container}>
      <TextInput
        style={s.search}
        placeholder="Search city, name, type..."
        placeholderTextColor="#555"
        value={search}
        onChangeText={setSearch}
        onSubmitEditing={load}
        returnKeyType="search"
      />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.filters} contentContainerStyle={s.filtersContent}>
        {STATUS_FILTERS.map((f) => (
          <TouchableOpacity
            key={f}
            style={[s.chip, status === f && s.chipActive]}
            onPress={() => setStatus(f)}
          >
            <Text style={[s.chipText, status === f && s.chipTextActive]}>{STATUS_LABELS[f]}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {loading
        ? <View style={s.center}><ActivityIndicator color="#7c6fff" /></View>
        : (
          <FlatList
            data={items}
            keyExtractor={(c) => String(c.id)}
            renderItem={({ item }) => (
              <ContactRow item={item} onPress={(id) => router.push({ pathname: '/(drawer)/contact-detail', params: { id } })} />
            )}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#7c6fff" />}
            contentContainerStyle={s.list}
            ListEmptyComponent={<Text style={s.empty}>No contacts found</Text>}
          />
        )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  search: { backgroundColor: '#1a1a2e', color: '#fff', borderRadius: 10, margin: 16, marginBottom: 8, padding: 12, fontSize: 14 },
  filters: { marginHorizontal: 16, marginBottom: 8 },
  filtersContent: { gap: 8 },
  chip: { borderRadius: 16, paddingHorizontal: 14, paddingVertical: 6, backgroundColor: '#ffffff10' },
  chipActive: { backgroundColor: '#7c6fff' },
  chipText: { color: '#888', fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: '#fff' },
  list: { padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { color: '#555', textAlign: 'center', marginTop: 60, fontSize: 15 },
});
```

- [ ] **Step 3: Create contact-detail.tsx**

Create `app/(drawer)/contact-detail.tsx`:

```typescript
import { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, ActivityIndicator, Linking, TouchableOpacity } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { fetchContact, ContactDetail } from '../../services/api';

export default function ContactDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [contact, setContact] = useState<ContactDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchContact(Number(id)).then(setContact).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <View style={s.center}><ActivityIndicator color="#7c6fff" /></View>;
  if (!contact) return <View style={s.center}><Text style={s.empty}>Contact not found</Text></View>;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <Text style={s.name}>{contact.name}</Text>
      <Text style={s.sub}>{contact.city}, {contact.country} · {contact.type}</Text>
      <View style={s.statusRow}>
        <Text style={s.statusBadge}>{contact.status}</Text>
        {contact.fit_score !== null && <Text style={s.score}>Score: {contact.fit_score}</Text>}
      </View>

      {contact.email && (
        <TouchableOpacity onPress={() => Linking.openURL(`mailto:${contact.email}`)}>
          <Text style={s.link}>{contact.email}</Text>
        </TouchableOpacity>
      )}
      {contact.website && (
        <TouchableOpacity onPress={() => Linking.openURL(contact.website!)}>
          <Text style={s.link}>{contact.website}</Text>
        </TouchableOpacity>
      )}
      {contact.phone && <Text style={s.field}>{contact.phone}</Text>}
      {contact.notes && (
        <View style={s.section}>
          <Text style={s.sectionTitle}>Notes</Text>
          <Text style={s.fieldText}>{contact.notes}</Text>
        </View>
      )}

      {contact.interactions.length > 0 && (
        <View style={s.section}>
          <Text style={s.sectionTitle}>History</Text>
          {contact.interactions.map((interaction, i) => (
            <View key={i} style={s.interaction}>
              <Text style={s.interactionType}>{interaction.interaction_type}</Text>
              <Text style={s.interactionDate}>{new Date(interaction.interaction_date).toLocaleDateString()}</Text>
              {interaction.notes && <Text style={s.interactionNotes}>{interaction.notes}</Text>}
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  content: { padding: 20 },
  center: { flex: 1, backgroundColor: '#0f0f23', justifyContent: 'center', alignItems: 'center' },
  name: { color: '#fff', fontSize: 22, fontWeight: '700', marginBottom: 4 },
  sub: { color: '#888', fontSize: 14, marginBottom: 12 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  statusBadge: { backgroundColor: '#7c6fff25', color: '#7c6fff', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12, fontSize: 12, fontWeight: '700' },
  score: { color: '#888', fontSize: 13 },
  link: { color: '#7c6fff', fontSize: 14, marginBottom: 8, textDecorationLine: 'underline' },
  field: { color: '#ccc', fontSize: 14, marginBottom: 8 },
  section: { marginTop: 20 },
  sectionTitle: { color: '#888', fontSize: 11, fontWeight: '700', letterSpacing: 1, marginBottom: 8, textTransform: 'uppercase' },
  fieldText: { color: '#ccc', fontSize: 14, lineHeight: 22 },
  interaction: { backgroundColor: '#1a1a2e', borderRadius: 8, padding: 12, marginBottom: 8 },
  interactionType: { color: '#7c6fff', fontSize: 12, fontWeight: '700', marginBottom: 2 },
  interactionDate: { color: '#666', fontSize: 11, marginBottom: 4 },
  interactionNotes: { color: '#aaa', fontSize: 13 },
  empty: { color: '#555' },
});
```

- [ ] **Step 4: Commit**

```bash
git add components/ContactRow.tsx "app/(drawer)/contacts.tsx" "app/(drawer)/contact-detail.tsx"
git commit -m "feat: add Contacts screen and Contact Detail screen"
```

---

## Task 12: Activity, Marketing, and Research screens

**Files:**

- Create: `app/(drawer)/activity.tsx`
- Create: `app/(drawer)/marketing.tsx`
- Create: `app/(drawer)/research.tsx`

- [ ] **Step 1: Create activity.tsx**

Create `app/(drawer)/activity.tsx`:

```typescript
import { useState, useCallback } from 'react';
import { View, FlatList, Text, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { fetchActivity, AgentRun } from '../../services/api';

const STATUS_COLOR = { running: '#eab308', completed: '#22c55e', failed: '#ef4444' };

export default function ActivityScreen() {
  const [items, setItems] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setItems(await fetchActivity()); } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (loading) return <View style={s.center}><ActivityIndicator color="#7c6fff" /></View>;

  return (
    <View style={s.container}>
      <FlatList
        data={items}
        keyExtractor={(r) => String(r.id)}
        renderItem={({ item }) => {
          const color = STATUS_COLOR[item.status] ?? '#888';
          return (
            <View style={[s.item, { borderLeftColor: color }]}>
              <Text style={s.agent}>{item.agent_name}</Text>
              <Text style={[s.status, { color }]}>{item.status}</Text>
              {item.summary && <Text style={s.summary}>{item.summary}</Text>}
              <Text style={s.time}>{new Date(item.started_at).toLocaleString()}</Text>
            </View>
          );
        }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#7c6fff" />}
        contentContainerStyle={s.list}
        ListEmptyComponent={<Text style={s.empty}>No activity yet</Text>}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  list: { padding: 16 },
  center: { flex: 1, backgroundColor: '#0f0f23', justifyContent: 'center', alignItems: 'center' },
  item: { backgroundColor: '#1a1a2e', borderRadius: 10, padding: 14, marginBottom: 8, borderLeftWidth: 3 },
  agent: { color: '#fff', fontSize: 14, fontWeight: '700', marginBottom: 2 },
  status: { fontSize: 12, fontWeight: '600', marginBottom: 4 },
  summary: { color: '#888', fontSize: 12, marginBottom: 4 },
  time: { color: '#555', fontSize: 11 },
  empty: { color: '#555', textAlign: 'center', marginTop: 60, fontSize: 15 },
});
```

- [ ] **Step 2: Create marketing.tsx**

Create `app/(drawer)/marketing.tsx`:

```typescript
import { useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { fetchObservations, fetchStrategies, fetchDigests, MarketingItem } from '../../services/api';

type Tab = 'observations' | 'strategies' | 'digests';

export default function MarketingScreen() {
  const [tab, setTab] = useState<Tab>('observations');
  const [data, setData] = useState<MarketingItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const fn = tab === 'observations' ? fetchObservations
        : tab === 'strategies' ? fetchStrategies
        : fetchDigests;
      setData(await fn());
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={s.container}>
      <View style={s.tabs}>
        {(['observations', 'strategies', 'digests'] as Tab[]).map((t) => (
          <TouchableOpacity key={t} style={[s.tab, tab === t && s.tabActive]} onPress={() => setTab(t)}>
            <Text style={[s.tabText, tab === t && s.tabTextActive]}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      {loading
        ? <View style={s.center}><ActivityIndicator color="#7c6fff" /></View>
        : (
          <ScrollView contentContainerStyle={s.list}>
            {data.length === 0 && <Text style={s.empty}>Nothing here yet</Text>}
            {data.map((item) => (
              <View key={item.id} style={s.card}>
                {Object.entries(item)
                  .filter(([k]) => !['id'].includes(k))
                  .map(([k, v]) => (
                    <Text key={k} style={s.row}>
                      <Text style={s.key}>{k}: </Text>
                      <Text style={s.val}>{String(v ?? '')}</Text>
                    </Text>
                  ))}
              </View>
            ))}
          </ScrollView>
        )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  tabs: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: '#ffffff15' },
  tab: { flex: 1, padding: 14, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#7c6fff' },
  tabText: { color: '#666', fontSize: 13, fontWeight: '600' },
  tabTextActive: { color: '#7c6fff' },
  list: { padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  card: { backgroundColor: '#1a1a2e', borderRadius: 10, padding: 14, marginBottom: 10 },
  row: { fontSize: 13, marginBottom: 4 },
  key: { color: '#888' },
  val: { color: '#ccc' },
  empty: { color: '#555', textAlign: 'center', marginTop: 60, fontSize: 15 },
});
```

- [ ] **Step 3: Create research.tsx**

Create `app/(drawer)/research.tsx`:

```typescript
import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, Alert, ActivityIndicator,
} from 'react-native';
import { runResearch } from '../../services/api';

const LEVELS = [1, 2, 3, 4, 5];
const COUNTRIES = [{ code: 'DE', label: 'Germany' }, { code: 'AT', label: 'Austria' }];

export default function ResearchScreen() {
  const [city, setCity] = useState('');
  const [level, setLevel] = useState(1);
  const [country, setCountry] = useState('DE');
  const [loading, setLoading] = useState(false);

  async function handleRun() {
    if (!city.trim()) {
      Alert.alert('City required', 'Please enter a city name.');
      return;
    }
    setLoading(true);
    try {
      await runResearch(city.trim(), level, country);
      Alert.alert('Scan queued', `Level ${level} scan for ${city} has started. Check Activity for progress.`);
      setCity('');
    } catch {
      Alert.alert('Error', 'Could not start scan. Try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={s.container}>
      <Text style={s.label}>City</Text>
      <TextInput
        style={s.input}
        placeholder="e.g. München"
        placeholderTextColor="#555"
        value={city}
        onChangeText={setCity}
        autoCapitalize="words"
      />

      <Text style={s.label}>Level</Text>
      <View style={s.row}>
        {LEVELS.map((l) => (
          <TouchableOpacity
            key={l}
            style={[s.levelBtn, level === l && s.levelBtnActive]}
            onPress={() => setLevel(l)}
          >
            <Text style={[s.levelText, level === l && s.levelTextActive]}>{l}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={s.label}>Country</Text>
      <View style={s.row}>
        {COUNTRIES.map((c) => (
          <TouchableOpacity
            key={c.code}
            style={[s.countryBtn, country === c.code && s.levelBtnActive]}
            onPress={() => setCountry(c.code)}
          >
            <Text style={[s.levelText, country === c.code && s.levelTextActive]}>{c.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={s.runBtn} onPress={handleRun} disabled={loading}>
        {loading
          ? <ActivityIndicator color="#fff" />
          : <Text style={s.runText}>Run Scan</Text>}
      </TouchableOpacity>

      <Text style={s.hint}>Results appear in the Activity screen.</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23', padding: 24 },
  label: { color: '#888', fontSize: 12, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10, marginTop: 20 },
  input: { backgroundColor: '#1a1a2e', color: '#fff', borderRadius: 10, padding: 14, fontSize: 16, borderWidth: 1, borderColor: '#ffffff20' },
  row: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  levelBtn: { backgroundColor: '#ffffff10', borderRadius: 10, width: 48, height: 48, justifyContent: 'center', alignItems: 'center' },
  levelBtnActive: { backgroundColor: '#7c6fff' },
  levelText: { color: '#888', fontSize: 16, fontWeight: '700' },
  levelTextActive: { color: '#fff' },
  countryBtn: { backgroundColor: '#ffffff10', borderRadius: 10, paddingHorizontal: 20, height: 48, justifyContent: 'center', alignItems: 'center' },
  runBtn: { marginTop: 36, backgroundColor: '#7c6fff', borderRadius: 12, padding: 18, alignItems: 'center' },
  runText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  hint: { color: '#555', fontSize: 12, textAlign: 'center', marginTop: 16 },
});
```

- [ ] **Step 4: Commit**

```bash
git add "app/(drawer)/activity.tsx" "app/(drawer)/marketing.tsx" "app/(drawer)/research.tsx"
git commit -m "feat: add Activity, Marketing, and Research screens"
```

---

## Task 13: Run all tests and verify in emulator

- [ ] **Step 1: Run full test suite**

```bash
npx jest --coverage
```

Expected: all tests pass. Coverage report printed.

- [ ] **Step 2: Start the app in Android emulator**

```bash
npx expo start --android
```

- [ ] **Step 3: Verify the golden path**

Walk through each screen manually in the emulator:

1. Login screen appears on first launch
2. Enter the admin password → redirected to Approvals
3. Open drawer → all 6 sections listed
4. Approvals → list loads, tap Reject → sheet slides up, enter reason, confirm
5. Inbox → list loads, tap Classify → sheet shows options
6. Contacts → list loads, search works, tap contact → detail screen
7. Activity → list loads, pull-to-refresh works
8. Marketing → tabs switch between Observations/Strategies/Digests
9. Research → enter city, select level, tap Run Scan → success alert
10. Log out via header button → returns to Login

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "chore: final test run and emulator verification"
```

---

## Task 14: Build APK with EAS

- [ ] **Step 1: Install EAS CLI**

```bash
npm install -g eas-cli
eas login
```

Log in with the Expo account.

- [ ] **Step 2: Configure EAS project**

```bash
eas build:configure
```

Expected: `eas.json` updated with project ID.

- [ ] **Step 3: Build preview APK**

```bash
eas build --platform android --profile preview
```

This runs in the cloud (~15 min on free tier). A URL to download the APK is printed when done.

- [ ] **Step 4: Install on phone**

Download the APK from the EAS dashboard URL and install via `adb`:

```bash
adb install artcrm.apk
```

Or transfer to the phone and install directly (enable "Install from unknown sources" in Android settings).

- [ ] **Step 5: Smoke test on real device**

Login, approve one draft, classify one inbox message. Confirm push notifications arrive when a new approval is queued (requires backend to be live and push token registered).

- [ ] **Step 6: Final commit and push**

```bash
git push
```
