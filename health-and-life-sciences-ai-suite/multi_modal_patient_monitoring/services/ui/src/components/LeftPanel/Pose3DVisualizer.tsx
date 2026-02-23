import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

interface Joint {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}

interface Person {
  person_id: number;
  joints_3d: Joint[];
  confidence?: number[];
}

interface Pose3DVisualizerProps {
  people: Person[];
  isExpanded: boolean;
}

// ✅ Configuration constants
const SPHERE_RADIUS = 5;
const LINE_WIDTH = 3;
const SPHERE_SEGMENTS = 16;
const LINE_OPACITY = 0.9;

// ✅ Exact skeleton connections from backend (engine3js.py)
const POSE_CONNECTIONS: [number, number][] = [
  [0, 1],    // neck-nose
  [1, 16],   // nose-left eye
  [16, 18],  // left eye-left ear
  [1, 15],   // nose-right eye
  [15, 17],  // right eye-right ear
  [0, 3],    // neck-left shoulder
  [3, 4],    // left shoulder-left elbow
  [4, 5],    // left elbow-left wrist
  [0, 9],    // neck-right shoulder
  [9, 10],   // right shoulder-right elbow
  [10, 11],  // right elbow-right wrist
  [0, 6],    // neck-left hip
  [6, 7],    // left hip-left knee
  [7, 8],    // left knee-left ankle
  [0, 12],   // neck-right hip
  [12, 13],  // right hip-right knee
  [13, 14],  // right knee-right ankle
];

// ✅ Single color scheme for all people
const SKELETON_COLOR = {
  sphere: 0x00ff00,  // Green for joint spheres
  line: 0xffff00     // Yellow for connecting lines
};

// ✅ Grid and Axes Configuration
const SHOW_GRID = true;           // Set to false to hide grid
const SHOW_AXES = true;           // Set to false to hide axes
const GRID_SIZE = 1000;            // Size of the grid
const GRID_DIVISIONS = 20;        // Number of divisions
const GRID_COLOR_CENTER = 0x333333;  // Color of center lines
const GRID_COLOR_GRID = 0x222222;    // Color of grid lines
const GRID_Y_POSITION = -120;     // Vertical position of grid
const AXES_SIZE = 40;            // Length of axes lines

const Pose3DVisualizer: React.FC<Pose3DVisualizerProps> = ({ people, isExpanded }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    renderer: THREE.WebGLRenderer;
    controls: OrbitControls;
    peopleObjects: Array<{
      spheres: THREE.Mesh[];
      lines: THREE.Line[];
    }>;
  } | null>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    const camera = new THREE.PerspectiveCamera(
      75,
      mountRef.current.clientWidth / mountRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0, 300);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Grid helper
    if (SHOW_GRID) {
      const gridHelper = new THREE.GridHelper(
        GRID_SIZE,              // Size
        GRID_DIVISIONS,         // Divisions
        GRID_COLOR_CENTER,      // Color 1 (center line)
        GRID_COLOR_GRID         // Color 2 (grid)
      );
      gridHelper.position.y = GRID_Y_POSITION;
      scene.add(gridHelper);
    }

    // Axes helper (Red = X, Green = Y, Blue = Z)
    if (SHOW_AXES && AXES_SIZE > 0) {
      const axesHelper = new THREE.AxesHelper(AXES_SIZE);
      axesHelper.position.y = GRID_Y_POSITION; // ✅ Move axes to same level as grid
      scene.add(axesHelper);
    }

    const peopleObjects: Array<{ spheres: THREE.Mesh[]; lines: THREE.Line[] }> = [];

    for (let personIdx = 0; personIdx < 5; personIdx++) {
      const spheres: THREE.Mesh[] = [];
      const lines: THREE.Line[] = [];

      for (let i = 0; i < 19; i++) {
        const geometry = new THREE.SphereGeometry(SPHERE_RADIUS, SPHERE_SEGMENTS, SPHERE_SEGMENTS);
        const material = new THREE.MeshPhongMaterial({
          color: SKELETON_COLOR.sphere,
          emissive: SKELETON_COLOR.sphere,
          emissiveIntensity: 0.5,
        });
        const sphere = new THREE.Mesh(geometry, material);
        sphere.visible = false;
        scene.add(sphere);
        spheres.push(sphere);
      }

      // ✅ Create line objects for fixed POSE_CONNECTIONS
      POSE_CONNECTIONS.forEach(([start, end]) => {
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array([0, 0, 0, 0, 0, 0]);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const material = new THREE.LineBasicMaterial({
          color: SKELETON_COLOR.line,
          linewidth: LINE_WIDTH,
          transparent: true,
          opacity: LINE_OPACITY,
        });

        const line = new THREE.Line(geometry, material);
        line.visible = false;
        scene.add(line);
        lines.push(line);
      });

      peopleObjects.push({ spheres, lines });
    }

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
    directionalLight.position.set(50, 100, 50);
    scene.add(directionalLight);

    sceneRef.current = { scene, camera, renderer, controls, peopleObjects };

    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!mountRef.current) return;
      camera.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    if (!sceneRef.current) return;

    const { peopleObjects } = sceneRef.current;

    peopleObjects.forEach(({ spheres, lines }) => {
      spheres.forEach(sphere => sphere.visible = false);
      lines.forEach(line => line.visible = false);
    });

    if (!people || people.length === 0) {
      return;
    }

    people.forEach((person, personIdx) => {
      if (personIdx >= peopleObjects.length) {
        return;
      }

      const { spheres, lines } = peopleObjects[personIdx];
      const joints = person.joints_3d;

      if (!joints || joints.length === 0) return;

      // Update joint positions
      joints.forEach((joint, i) => {
        if (i >= spheres.length) return;

        const sphere = spheres[i];

        if (joint.x !== -1 && joint.y !== -1 && joint.z !== -1) {
          sphere.position.set(joint.x, -joint.y, -joint.z);
          sphere.visible = true;

          const material = sphere.material as THREE.MeshPhongMaterial;
          const visibility = joint.visibility !== undefined ? joint.visibility : 1.0;
          const intensity = Math.max(0.5, visibility);
          
          const baseColor = new THREE.Color(SKELETON_COLOR.sphere);
          material.color.copy(baseColor).multiplyScalar(intensity);
          material.emissive.copy(baseColor).multiplyScalar(intensity * 0.5);
        } else {
          sphere.visible = false;
        }
      });

      // ✅ Update connections using fixed anatomical structure
      POSE_CONNECTIONS.forEach(([startIdx, endIdx], lineIdx) => {
        if (lineIdx >= lines.length) return;

        const line = lines[lineIdx];
        const startJoint = joints[startIdx];
        const endJoint = joints[endIdx];

        if (
          startJoint && endJoint &&
          startJoint.x !== -1 && startJoint.y !== -1 && startJoint.z !== -1 &&
          endJoint.x !== -1 && endJoint.y !== -1 && endJoint.z !== -1
        ) {
          const geometry = line.geometry as THREE.BufferGeometry;
          const positions = geometry.attributes.position.array as Float32Array;

          positions[0] = startJoint.x;
          positions[1] = -startJoint.y;
          positions[2] = -startJoint.z;
          positions[3] = endJoint.x;
          positions[4] = -endJoint.y;
          positions[5] = -endJoint.z;

          geometry.attributes.position.needsUpdate = true;
          line.visible = true;
        } else {
          line.visible = false;
        }
      });
    });
  }, [people]);

  return (
    <div
      ref={mountRef}
      style={{
        width: '100%',
        height: isExpanded ? '400px' : '200px',
        borderRadius: '8px',
        border: '1px solid #333',
        overflow: 'hidden',
        backgroundColor: '#000000',
        position: 'relative',
      }}
    >
      {(!people || people.length === 0) && (
        <div style={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          textAlign: 'right',
          color: '#cccccc',
          fontSize: '12px',
          pointerEvents: 'none',
          zIndex: 1,
          background: 'rgba(0, 0, 0, 0.7)',
          padding: '8px 12px',
          borderRadius: '6px',
          border: '1px solid #444'
        }}>
          <div>No person detected</div>
        </div>
      )}
      
      {people && people.length > 1 && (
        <div style={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          background: 'rgba(0, 0, 0, 0.8)',
          padding: '8px 12px',
          borderRadius: '6px',
          fontSize: '11px',
          color: '#fff',
          zIndex: 1,
          border: '1px solid #444'
        }}>
          <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '12px' }}>
            Detected: {people.length} {people.length === 1 ? 'person' : 'people'}
          </div>
          {people.map((person, idx) => (
            <div key={person.person_id} style={{ 
              marginBottom: '4px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px' 
            }}>
              <div style={{
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                backgroundColor: '#00ff00',
                boxShadow: '0 0 8px #00ff00'
              }}></div>
              <span>Person {person.person_id + 1}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Pose3DVisualizer;