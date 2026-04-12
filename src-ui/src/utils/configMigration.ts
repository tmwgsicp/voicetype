/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 * 
 * Frontend Configuration Version Management
 * 
 * Design:
 * - Version-based migration system matching backend
 * - Declarative migration functions
 * - Type-safe config merging (no Object.assign overwrite)
 * - Clear upgrade path for future versions
 */

// Current frontend config schema version (matches backend)
export const CURRENT_CONFIG_VERSION = 2 // v0.3.0

export interface ConfigData {
  config_version?: number
  [key: string]: any
}

/**
 * Migration: v0 → v1
 * Add config_version field
 */
function migrateV0ToV1(data: ConfigData): ConfigData {
  console.log('[Config Migration] v0 → v1')
  return {
    ...data,
    config_version: 1
  }
}

/**
 * Migration: v1 → v2 (v0.3.0)
 * 
 * Changes:
 * - Default ASR: aliyun → sherpa (local offline)
 * - Remove bundled API keys
 * - Keyring support for API keys
 */
function migrateV1ToV2(data: ConfigData): ConfigData {
  console.log('[Config Migration] v1 → v2 (v0.3.0)')
  
  const migrated = { ...data }
  
  // Detect legacy aliyun default with bundled key
  if (migrated.asr_provider === 'aliyun' && 
      migrated.asr_api_key && 
      migrated.asr_api_key.startsWith('sk-')) {
    console.warn('[Config Migration] Detected bundled API key, switching to local ASR')
    migrated.asr_provider = 'sherpa'
    migrated.asr_model = 'sherpa-local'
    delete migrated.asr_api_key
  }
  
  migrated.config_version = 2
  return migrated
}

// Migration pipeline
type MigrationFunc = (data: ConfigData) => ConfigData

const MIGRATIONS: Array<{ targetVersion: number; migrate: MigrationFunc }> = [
  { targetVersion: 1, migrate: migrateV0ToV1 },
  { targetVersion: 2, migrate: migrateV1ToV2 },
]

/**
 * Apply all necessary migrations to bring config to current version
 */
export function applyMigrations(data: ConfigData): ConfigData {
  const currentVersion = data.config_version ?? 0
  
  if (currentVersion === CURRENT_CONFIG_VERSION) {
    console.log(`[Config Migration] Already at v${CURRENT_CONFIG_VERSION}, no migration needed`)
    return data
  }
  
  if (currentVersion > CURRENT_CONFIG_VERSION) {
    console.warn(
      `[Config Migration] Config v${currentVersion} > app v${CURRENT_CONFIG_VERSION}. ` +
      'May be from newer VoiceType version, attempting to load anyway...'
    )
    return data
  }
  
  console.log(`[Config Migration] Starting: v${currentVersion} → v${CURRENT_CONFIG_VERSION}`)
  
  let migrated = { ...data }
  
  for (const { targetVersion, migrate } of MIGRATIONS) {
    if (currentVersion < targetVersion) {
      try {
        migrated = migrate(migrated)
        console.log(`[Config Migration] ✓ v${targetVersion} complete`)
      } catch (error) {
        console.error(`[Config Migration] ✗ v${targetVersion} failed:`, error)
        throw error
      }
    }
  }
  
  return migrated
}

/**
 * Type-safe config merge: only update fields that exist in defaults
 * Prevents old config from overwriting new default values
 * 
 * @param defaults - Default config object (with correct types)
 * @param serverData - Data from server (may have old/missing fields)
 * @returns Merged config object
 */
export function mergeConfig<T extends Record<string, any>>(
  defaults: T,
  serverData: Partial<T>
): T {
  const merged = { ...defaults }
  
  for (const key in serverData) {
    // Only update fields that exist in defaults
    if (key in defaults) {
      ;(merged as any)[key] = serverData[key]
    } else {
      console.warn(`[Config Merge] Ignoring unknown field: ${key}`)
    }
  }
  
  return merged
}

/**
 * Full config load pipeline with migration and merge
 * 
 * Usage in SettingsView.vue:
 * ```
 * const serverData = await api.getConfig()
 * const migrated = applyMigrations(serverData)
 * const final = mergeConfig(config, migrated)
 * Object.assign(config, final)
 * ```
 */
export function loadConfigWithMigration<T extends ConfigData>(
  defaults: T,
  serverData: ConfigData
): T {
  // Step 1: Apply migrations
  const migrated = applyMigrations(serverData)
  
  // Step 2: Type-safe merge
  const merged = mergeConfig(defaults, migrated as Partial<T>)
  
  return merged
}
