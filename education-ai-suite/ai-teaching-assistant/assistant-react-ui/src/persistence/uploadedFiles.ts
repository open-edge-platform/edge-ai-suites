// Persists the uploaded knowledge-base files in IndexedDB so the list (and the
// underlying file bytes needed for re-ingestion) survive a page refresh. The
// files are only cleared when the user removes them or when the backend context
// has been reset (e.g. by stop_ata), which is reconciled on startup in App.tsx.

const DB_NAME = "ata-knowledge-base";
const STORE_NAME = "uploaded-files";
const RECORD_KEY = "files";

interface StoredFile {
  name: string;
  size: number;
  type: string;
  lastModified: number;
  blob: Blob;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveUploadedFiles(files: File[]): Promise<void> {
  const records: StoredFile[] = files.map((f) => ({
    name: f.name,
    size: f.size,
    type: f.type,
    lastModified: f.lastModified,
    blob: f.slice(0, f.size, f.type),
  }));
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).put(records, RECORD_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

export async function loadUploadedFiles(): Promise<File[]> {
  const db = await openDb();
  try {
    const records = await new Promise<StoredFile[] | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const req = tx.objectStore(STORE_NAME).get(RECORD_KEY);
      req.onsuccess = () => resolve(req.result as StoredFile[] | undefined);
      req.onerror = () => reject(req.error);
    });
    if (!records) return [];
    return records.map(
      (r) => new File([r.blob], r.name, { type: r.type, lastModified: r.lastModified })
    );
  } finally {
    db.close();
  }
}

export async function clearUploadedFiles(): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).delete(RECORD_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}
