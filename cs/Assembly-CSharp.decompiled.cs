using System;
using System.Reflection;
using System.Runtime.CompilerServices;
using UnityEngine;

[assembly: RuntimeCompatibility(WrapNonExceptionThrows = true)]
[assembly: AssemblyVersion("0.0.0.0")]
public class HorseMove : MonoBehaviour
{
	private float rotation;

	private Vector3 movement = default;

	private Terrain terrain;

	private Animator animator;

	private void Start()
	{
		terrain = GameObject.Find("Terrain").GetComponent<Terrain>();
		animator = transform.FindChild("Horse").GetComponent<Animator>();
		animator.Play("Horse_Idle");
	}

	private void Update()
	{
		movement *= Mathf.Pow(0.01f, Time.deltaTime * 10f);
		if (Input.GetKey(KeyCode.W))
		{
			movement.x += Mathf.Sin(rotation * (float)Math.PI / 180f);
			movement.z += Mathf.Cos(rotation * (float)Math.PI / 180f);
			animator.Play("Horse_Run");
		}
		else if (Input.GetKey(KeyCode.S))
		{
			movement.x -= Mathf.Sin(rotation * (float)Math.PI / 180f);
			movement.z -= Mathf.Cos(rotation * (float)Math.PI / 180f);
			animator.Play("Horse_Run");
		}
		else
		{
			animator.Play("Horse_Idle");
		}
		if (Input.GetKey(KeyCode.A))
		{
			rotation -= 80f * Time.deltaTime;
		}
		if (Input.GetKey(KeyCode.D))
		{
			rotation += 80f * Time.deltaTime;
		}
		Vector3 interpolatedNormal = terrain.terrainData.GetInterpolatedNormal(transform.position.x / terrain.terrainData.size.x, transform.position.z / terrain.terrainData.size.z);
		CharacterController component = GetComponent<CharacterController>();
		Vector3 lhs = new Vector3(Mathf.Cos(rotation * (float)Math.PI / 180f), 0f, 0f - Mathf.Sin(rotation * (float)Math.PI / 180f));
		component.transform.rotation = Quaternion.LookRotation(Vector3.Cross(lhs, interpolatedNormal), interpolatedNormal);
		movement.y = -10f;
		component.Move(movement * Time.deltaTime * 10f);
	}

	private void OnControllerColliderHit(ControllerColliderHit hit)
	{
		Rigidbody attachedRigidbody = hit.collider.attachedRigidbody;
		if (!(attachedRigidbody == null) && !attachedRigidbody.isKinematic && !((double)hit.moveDirection.y < -0.3))
		{
			Vector3 vector = new Vector3(hit.moveDirection.x, 0f, hit.moveDirection.z);
			attachedRigidbody.velocity = vector * 50.2f;
		}
	}
}
public class LookAtHorse : MonoBehaviour
{
	private Transform horseTransform;

	private void Start()
	{
		horseTransform = GameObject.Find("Horse").transform;
	}

	private void Update()
	{
		camera.transform.LookAt(horseTransform.TransformPoint(new Vector3(0f, 3f, 1f)));
	}
}
