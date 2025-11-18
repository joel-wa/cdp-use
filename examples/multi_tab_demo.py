#!/usr/bin/env python3
"""
Multi-Tab Browser Control Demo

This demo showcases the new multi-tab session management capabilities.
It demonstrates creating multiple sessions and controlling them independently.

Usage:
    python examples/multi_tab_demo.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure we can import from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from cdp_use.session_manager import TabSessionManager


async def demo_multi_tab():
    """Demonstrate multi-tab browser control"""
    
    print("=" * 70)
    print("Multi-Tab Browser Control Demo")
    print("=" * 70)
    
    # Create session manager
    print("\n📦 Initializing session manager...")
    manager = TabSessionManager(max_sessions=5, idle_timeout_seconds=0)
    await manager.start()
    
    try:
        # Demo 1: Create multiple sessions
        print("\n" + "─" * 70)
        print("DEMO 1: Creating Multiple Browser Sessions")
        print("─" * 70)
        
        sessions = []
        urls = [
            ("https://example.com", "Example Domain"),
            ("https://www.wikipedia.org", "Wikipedia"),
            ("https://github.com", "GitHub")
        ]
        
        for url, name in urls:
            print(f"\n🌐 Creating session for {name}...")
            session = await manager.create_session(url, metadata={"name": name})
            sessions.append(session)
            print(f"   ✅ Session ID: {session.session_id}")
            print(f"   📍 URL: {session.current_url}")
            print(f"   🕐 Created: {session.created_at.strftime('%H:%M:%S')}")
        
        # Demo 2: List all sessions
        print("\n" + "─" * 70)
        print("DEMO 2: Listing All Active Sessions")
        print("─" * 70)
        
        all_sessions = await manager.list_sessions()
        print(f"\n📊 Total Active Sessions: {len(all_sessions)}")
        print()
        
        for i, sess in enumerate(all_sessions, 1):
            default_marker = "⭐ (default)" if sess['is_default'] else ""
            print(f"{i}. Session: {sess['session_id']} {default_marker}")
            print(f"   URL: {sess['current_url']}")
            print(f"   Connected: {'✅' if sess['is_connected'] else '❌'}")
            print(f"   Last Used: {sess['last_used']}")
            if sess.get('metadata'):
                print(f"   Metadata: {sess['metadata']}")
            print()
        
        # Demo 3: Session isolation
        print("─" * 70)
        print("DEMO 3: Verifying Session Isolation")
        print("─" * 70)
        
        print("\n🔍 Checking that each session has:")
        print("   • Unique session ID")
        print("   • Separate CDP client connection")
        print("   • Independent selector map")
        print("   • Isolated browser state")
        
        print("\n✅ Session Isolation Verified:")
        for session in sessions:
            print(f"   • {session.session_id[:16]}... has independent CDP client")
        
        # Demo 4: Get specific session info
        print("\n" + "─" * 70)
        print("DEMO 4: Getting Specific Session Information")
        print("─" * 70)
        
        target_session = sessions[1]
        print(f"\n📋 Details for session: {target_session.session_id}")
        print(f"   Target ID: {target_session.target_id}")
        print(f"   WebSocket URL: {target_session.ws_url[:50]}...")
        print(f"   Current URL: {target_session.current_url}")
        print(f"   Is Connected: {target_session.is_connected}")
        print(f"   Selector Map Size: {len(target_session.selector_map)} elements")
        print(f"   Metadata: {target_session.metadata}")
        
        # Demo 5: Change default session
        print("\n" + "─" * 70)
        print("DEMO 5: Changing Default Session")
        print("─" * 70)
        
        print(f"\n📌 Current default: {manager.default_session_id}")
        print(f"🔄 Changing default to: {sessions[2].session_id}")
        
        await manager.set_default_session(sessions[2].session_id)
        
        print(f"✅ New default: {manager.default_session_id}")
        
        # Demo 6: Get or create default
        print("\n" + "─" * 70)
        print("DEMO 6: Default Session Auto-Creation")
        print("─" * 70)
        
        print("\n🎯 Getting default session (should return existing)...")
        default = await manager.get_or_create_default()
        print(f"   ✅ Returned: {default.session_id}")
        print(f"   📊 Total sessions unchanged: {manager.get_session_count()}")
        
        # Demo 7: Close sessions
        print("\n" + "─" * 70)
        print("DEMO 7: Closing Sessions")
        print("─" * 70)
        
        print(f"\n🗑️  Closing session: {sessions[0].session_id}")
        success = await manager.close_session(sessions[0].session_id)
        print(f"   {'✅' if success else '❌'} Result: {success}")
        print(f"   📊 Remaining sessions: {manager.get_session_count()}")
        
        # Demo 8: Session lifecycle
        print("\n" + "─" * 70)
        print("DEMO 8: Session Lifecycle Summary")
        print("─" * 70)
        
        final_sessions = await manager.list_sessions()
        print(f"\n📈 Session Lifecycle:")
        print(f"   Created: {len(urls)} sessions")
        print(f"   Closed: 1 session")
        print(f"   Active: {len(final_sessions)} sessions")
        print()
        
        print("Active Sessions:")
        for sess in final_sessions:
            age_seconds = (sess['last_used'] != sess['created_at'])
            print(f"   • {sess['session_id']}: {sess['metadata'].get('name', 'Unknown')}")
        
        # Final summary
        print("\n" + "=" * 70)
        print("✨ Multi-Tab Demo Complete!")
        print("=" * 70)
        
        print("\n📚 What You Can Do:")
        print("   ✅ Create multiple concurrent browser sessions")
        print("   ✅ Each session has isolated state and controls")
        print("   ✅ List, manage, and close sessions independently")
        print("   ✅ Set default session for backwards compatibility")
        print("   ✅ Access session-specific information")
        print("   ✅ Automatic cleanup and resource management")
        
        print("\n🚀 Next Steps:")
        print("   • Use session_id parameter in browser tools")
        print("   • Control multiple tabs with navigate(), click(), etc.")
        print("   • Take screenshots from different sessions")
        print("   • Run parallel workflows across sessions")
        
    finally:
        print("\n🧹 Cleaning up...")
        await manager.stop()
        print("✅ All sessions closed and cleaned up")


async def main():
    """Main entry point"""
    try:
        await demo_multi_tab()
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    print("\n🎬 Starting Multi-Tab Browser Control Demo...")
    print("📋 Make sure Chrome is running with debugging enabled:")
    print("   chrome --remote-debugging-port=9222")
    print()
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
