pub mod backend;
pub mod protocol;

use backend::{
    backend_request, backend_restart, backend_shutdown, backend_snapshot, backend_start,
    BackendManager,
};
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(BackendManager::new(app.handle().clone()));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            backend_start,
            backend_snapshot,
            backend_request,
            backend_shutdown,
            backend_restart
        ])
        .build(tauri::generate_context!())
        .expect("failed to build the Research Agent desktop shell");
    app.run(|app_handle, event| match event {
        tauri::RunEvent::ExitRequested { .. } => {
            app_handle.state::<BackendManager>().shutdown_best_effort();
        }
        tauri::RunEvent::Exit => {
            app_handle.state::<BackendManager>().shutdown_best_effort();
        }
        _ => {}
    });
}
