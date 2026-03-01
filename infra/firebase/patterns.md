# Firebase - Patrones de Infraestructura

> jps_dev_engine v3.5.0 | Referencia de patrones para proyectos basados en Firebase

---

## 1. Cuando usar Firebase vs Supabase

| Criterio | Firebase | Supabase |
|----------|----------|----------|
| Base de datos relacional | No (NoSQL) | Si (Postgres) |
| Consultas complejas (joins) | Limitado | Completo |
| Realtime granular | Excelente | Bueno |
| Autenticacion social | Nativo | Nativo |
| Hosting + Functions integrado | Si | Edge Functions |
| Flutter SDK maduro | Muy maduro | Maduro |
| Costo predecible | Dificil (por lectura) | Mas predecible |

**Regla general:** Usar Firebase cuando el modelo de datos es jerarquico/documental, se necesita sincronizacion offline robusta, o el equipo ya tiene experiencia con el ecosistema Google.

---

## 2. Firestore - Reglas de seguridad

### Estructura base

```javascript
rules_version = '2';
service cloud.firestore {
    match /databases/{database}/documents {

        // Funciones auxiliares
        function isAuthenticated() {
            return request.auth != null;
        }

        function isOwner(userId) {
            return request.auth.uid == userId;
        }

        function hasRole(role) {
            return get(/databases/$(database)/documents/users/$(request.auth.uid))
                .data.role == role;
        }

        // Reglas por coleccion
        match /users/{userId} {
            allow read: if isAuthenticated();
            allow write: if isOwner(userId);
        }

        match /{collection}/{docId} {
            allow read: if isAuthenticated();
            allow create: if isAuthenticated()
                && request.resource.data.userId == request.auth.uid;
            allow update, delete: if isOwner(resource.data.userId);
        }
    }
}
```

### Patron: Lectura publica, escritura del propietario

```javascript
match /posts/{postId} {
    allow read: if true;
    allow create: if isAuthenticated();
    allow update, delete: if isOwner(resource.data.userId);
}
```

### Patron: Acceso basado en rol

```javascript
match /admin/{docId} {
    allow read, write: if hasRole('admin');
}
```

### Buenas practicas en reglas

- Nunca dejar reglas abiertas (`allow read, write: if true`) en produccion.
- Validar estructura de datos en las reglas (`request.resource.data.keys().hasAll()`).
- Usar funciones auxiliares para reutilizar logica.
- Probar reglas con el emulador antes de desplegar.

---

## 3. Flujos de autenticacion

### Proveedores recomendados

```
- Email/Password (basico)
- Google Sign-In (social)
- Apple Sign-In (requerido en iOS)
- Phone Auth (verificacion SMS)
```

### Flutter: Flujo con FirebaseAuth

```dart
// Email/Password
final credential = await FirebaseAuth.instance.signInWithEmailAndPassword(
    email: email,
    password: password,
);

// Google Sign-In
final googleUser = await GoogleSignIn().signIn();
final googleAuth = await googleUser?.authentication;
final credential = GoogleAuthProvider.credential(
    accessToken: googleAuth?.accessToken,
    idToken: googleAuth?.idToken,
);
await FirebaseAuth.instance.signInWithCredential(credential);
```

### Escuchar cambios de estado

```dart
FirebaseAuth.instance.authStateChanges().listen((User? user) {
    if (user == null) {
        // Usuario no autenticado
    } else {
        // Usuario autenticado
    }
});
```

### Regla: Crear documento de perfil tras registro

```dart
Future<void> createUserProfile(User user) async {
    final doc = FirebaseFirestore.instance.collection('users').doc(user.uid);
    final snapshot = await doc.get();
    if (!snapshot.exists) {
        await doc.set({
            'email': user.email,
            'displayName': user.displayName,
            'createdAt': FieldValue.serverTimestamp(),
        });
    }
}
```

---

## 4. Cloud Functions

### Estructura de proyecto

```
functions/
    src/
        index.ts
        triggers/
            on{Entity}Created.ts
            on{Entity}Updated.ts
        http/
            api{Feature}.ts
    package.json
    tsconfig.json
```

### Trigger de Firestore

```typescript
import { onDocumentCreated } from 'firebase-functions/v2/firestore';

export const onTaskCreated = onDocumentCreated(
    '{collection}/{docId}',
    async (event) => {
        const data = event.data?.data();
        const docId = event.params.docId;
        // Logica post-creacion (notificaciones, indices, etc.)
    }
);
```

### Funcion HTTP

```typescript
import { onRequest } from 'firebase-functions/v2/https';

export const api{Feature} = onRequest(async (req, res) => {
    // Verificar autenticacion si es necesario
    const token = req.headers.authorization?.split('Bearer ')[1];
    // Procesar peticion
    res.json({ status: 'ok' });
});
```

### Reglas de Cloud Functions

- Usar v2 de las funciones (firebase-functions/v2).
- Separar triggers de funciones HTTP.
- No escribir logica de negocio directamente en el handler; delegar a servicios.

---

## 5. Firebase Storage

### Reglas de seguridad para Storage

```javascript
rules_version = '2';
service firebase.storage {
    match /b/{bucket}/o {
        match /users/{userId}/{allPaths=**} {
            allow read: if request.auth != null;
            allow write: if request.auth.uid == userId
                && request.resource.size < 5 * 1024 * 1024
                && request.resource.contentType.matches('image/.*');
        }
    }
}
```

### Estructura de archivos

```
users/{userId}/avatar.jpg
users/{userId}/documents/{fileName}
public/{category}/{fileName}
```

### Subida desde Flutter

```dart
final ref = FirebaseStorage.instance.ref('users/${user.uid}/avatar.jpg');
await ref.putFile(file);
final url = await ref.getDownloadURL();
```

### Buenas practicas de Storage

- Limitar tamano de archivo en las reglas.
- Validar tipo de contenido (contentType) en las reglas.
- Usar estructura `{userId}/` para aislar archivos por usuario.
- Generar thumbnails con Cloud Functions tras la subida si es necesario.
