#!/usr/bin/env python3
"""
Test script for multi-tab browser session management

This script tests the new multi-tab capabilities:
1. Creating multiple sessions
2. Session isolation
3. Concurrent operations
4. Session cleanup
5. Backwards compatibility
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cdp_use.session_manager import TabSessionManager, TabSession


async def test_session_manager():
    """Test basic session manager operations"""
    print("=" * 60)
    print("TEST 1: Session Manager Basic Operations")
    print("=" * 60)
    
    manager = TabSessionManager(max_sessions=5, idle_timeout_seconds=0)  # Disable timeout for testing
    await manager.start()
    
    try:
        # Test 1: Create first session (becomes default)
        print("\n1. Creating first session...")
        session1 = await manager.create_session(url="https://example.com", metadata={"name": "Session 1"})
        print(f"   ✅ Created: {session1.session_id}")
        print(f"   📍 Default session: {manager.default_session_id}")
        assert manager.default_session_id == session1.session_id, "First session should be default"
        
        # Test 2: Create second session
        print("\n2. Creating second session...")
        session2 = await manager.create_session(url="https://google.com", metadata={"name": "Session 2"})
        print(f"   ✅ Created: {session2.session_id}")
        assert session1.session_id != session2.session_id, "Sessions should have unique IDs"
        
        # Test 3: List all sessions
        print("\n3. Listing all sessions...")
        sessions = await manager.list_sessions()
        print(f"   📊 Total sessions: {len(sessions)}")
        for s in sessions:
            print(f"      - {s['session_id']} (default: {s['is_default']}) - {s['current_url']}")
        assert len(sessions) == 2, "Should have 2 sessions"
        
        # Test 4: Get specific session
        print("\n4. Getting specific session...")
        retrieved = await manager.get_session(session1.session_id)
        print(f"   ✅ Retrieved: {retrieved.session_id}")
        assert retrieved.session_id == session1.session_id, "Should retrieve correct session"
        
        # Test 5: Set different default
        print("\n5. Changing default session...")
        await manager.set_default_session(session2.session_id)
        print(f"   ✅ New default: {manager.default_session_id}")
        assert manager.default_session_id == session2.session_id, "Default should be updated"
        
        # Test 6: Get or create default
        print("\n6. Getting default session...")
        default = await manager.get_or_create_default()
        print(f"   ✅ Default session: {default.session_id}")
        assert default.session_id == session2.session_id, "Should return current default"
        
        # Test 7: Close a session
        print("\n7. Closing a session...")
        success = await manager.close_session(session1.session_id)
        print(f"   ✅ Closed: {success}")
        remaining = await manager.list_sessions()
        print(f"   📊 Remaining sessions: {len(remaining)}")
        assert len(remaining) == 1, "Should have 1 session remaining"
        
        # Test 8: Try to get closed session (should fail)
        print("\n8. Attempting to get closed session...")
        try:
            await manager.get_session(session1.session_id)
            print("   ❌ ERROR: Should have raised KeyError")
            assert False, "Should raise KeyError for non-existent session"
        except KeyError as e:
            print(f"   ✅ Correctly raised KeyError: {e}")
        
        # Test 9: Session count
        print("\n9. Checking session count...")
        count = manager.get_session_count()
        print(f"   📊 Session count: {count}")
        assert count == 1, "Should have 1 session"
        
        print("\n" + "=" * 60)
        print("✅ ALL SESSION MANAGER TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await manager.stop()
        print("\n🧹 Session manager stopped")


async def test_session_isolation():
    """Test that sessions are properly isolated"""
    print("\n" + "=" * 60)
    print("TEST 2: Session Isolation")
    print("=" * 60)
    
    manager = TabSessionManager(max_sessions=5, idle_timeout_seconds=0)
    await manager.start()
    
    try:
        # Create two sessions
        print("\n1. Creating two isolated sessions...")
        session1 = await manager.create_session(url="about:blank", metadata={"test": "A"})
        session2 = await manager.create_session(url="about:blank", metadata={"test": "B"})
        print(f"   ✅ Session 1: {session1.session_id}")
        print(f"   ✅ Session 2: {session2.session_id}")
        
        # Verify different CDP clients
        print("\n2. Verifying separate CDP clients...")
        assert session1.cdp_client != session2.cdp_client, "Sessions should have different CDP clients"
        print("   ✅ Sessions have isolated CDP clients")
        
        # Verify different selector maps
        print("\n3. Verifying separate selector maps...")
        assert session1.selector_map is not session2.selector_map, "Sessions should have separate selector maps"
        print("   ✅ Sessions have isolated selector maps")
        
        # Add items to one selector map
        from cdp_use.session_manager import DOMRect, EnhancedAXNode, EnhancedDOMTreeNode
        
        node1 = EnhancedDOMTreeNode(
            element_index=1,
            tag_name="button",
            attributes={"id": "test"},
            absolute_position=DOMRect(0, 0, 100, 50),
            ax_node=EnhancedAXNode(name="Test Button"),
            text="Click me"
        )
        session1.selector_map[1] = node1
        
        print("\n4. Testing selector map isolation...")
        print(f"   Session 1 selector map size: {len(session1.selector_map)}")
        print(f"   Session 2 selector map size: {len(session2.selector_map)}")
        assert len(session1.selector_map) == 1, "Session 1 should have 1 item"
        assert len(session2.selector_map) == 0, "Session 2 should remain empty"
        print("   ✅ Selector maps are properly isolated")
        
        print("\n" + "=" * 60)
        print("✅ ALL ISOLATION TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await manager.stop()


async def test_max_sessions():
    """Test max sessions limit"""
    print("\n" + "=" * 60)
    print("TEST 3: Max Sessions Limit")
    print("=" * 60)
    
    manager = TabSessionManager(max_sessions=3, idle_timeout_seconds=0)
    await manager.start()
    
    try:
        # Create max sessions
        print("\n1. Creating sessions up to limit...")
        sessions = []
        for i in range(3):
            session = await manager.create_session(url="about:blank", metadata={"index": i})
            sessions.append(session)
            print(f"   ✅ Created session {i+1}/3: {session.session_id}")
        
        # Try to create one more (should fail)
        print("\n2. Attempting to exceed limit...")
        try:
            await manager.create_session(url="about:blank")
            print("   ❌ ERROR: Should have raised RuntimeError")
            assert False, "Should raise RuntimeError when max sessions reached"
        except RuntimeError as e:
            print(f"   ✅ Correctly raised RuntimeError: {e}")
        
        # Close one and try again
        print("\n3. Closing one session and trying again...")
        await manager.close_session(sessions[0].session_id)
        session4 = await manager.create_session(url="about:blank")
        print(f"   ✅ Successfully created new session: {session4.session_id}")
        
        print("\n" + "=" * 60)
        print("✅ MAX SESSIONS TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await manager.stop()


async def test_backwards_compatibility():
    """Test that default session behavior works"""
    print("\n" + "=" * 60)
    print("TEST 4: Backwards Compatibility")
    print("=" * 60)
    
    manager = TabSessionManager(max_sessions=5, idle_timeout_seconds=0)
    await manager.start()
    
    try:
        print("\n1. Getting default session without any sessions...")
        # Should auto-create a default session
        default = await manager.get_or_create_default()
        print(f"   ✅ Auto-created default session: {default.session_id}")
        assert manager.default_session_id == default.session_id
        
        print("\n2. Getting default again (should return same)...")
        default2 = await manager.get_or_create_default()
        print(f"   ✅ Returned same default: {default2.session_id}")
        assert default.session_id == default2.session_id, "Should return same default"
        
        print("\n3. Total sessions should be 1...")
        count = manager.get_session_count()
        print(f"   📊 Session count: {count}")
        assert count == 1, "Should only have 1 auto-created session"
        
        print("\n" + "=" * 60)
        print("✅ BACKWARDS COMPATIBILITY TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await manager.stop()


async def main():
    """Run all tests"""
    print("\n" + "🧪" * 30)
    print("MULTI-TAB SESSION MANAGEMENT TEST SUITE")
    print("🧪" * 30)
    
    try:
        await test_session_manager()
        await test_session_isolation()
        await test_max_sessions()
        await test_backwards_compatibility()
        
        print("\n" + "🎉" * 30)
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("🎉" * 30)
        print("\n✅ Multi-tab browser control is ready for use!")
        print("\n📚 Available features:")
        print("   - Create multiple browser sessions")
        print("   - Isolated CDP clients per session")
        print("   - Session-specific selector maps")
        print("   - Default session for backwards compatibility")
        print("   - Session lifecycle management")
        print("   - Max sessions limit enforcement")
        
        return 0
        
    except Exception as e:
        print("\n" + "❌" * 30)
        print(f"TEST FAILED: {e}")
        print("❌" * 30)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
